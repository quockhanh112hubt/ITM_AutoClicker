/* Experimental, opt-in virtual mouse for profile-selected Unity IL2CPP clients.
 * No global input, cursor movement, foreground activation, or disk patching.
 * MinHook is distributed separately under its included BSD license.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <wchar.h>
#include "MinHook.h"

typedef struct {
    uint32_t magic, version;
    uint64_t hwnd;
    uint32_t owner_pid, session;
    volatile LONG seq, ack, enabled, buttons, x, y, wheel, status;
    volatile ULONGLONG heartbeat;
    volatile LONG native_session, frame, position_reads, button_reads;
    volatile LONG updates, focus_overrides, error_code, reserved;
#ifdef MONO_BACKEND
    uint32_t keys[16];
    volatile LONG key_reads, client_width, client_height, render_width, render_height, padding;
#endif
} Shared;
#ifdef MONO_BACKEND
_Static_assert(sizeof(Shared) == 184, "Mono IPC layout mismatch");
#define IPC_VERSION 3
#else
_Static_assert(sizeof(Shared) == 96, "IPC layout mismatch");
#define IPC_VERSION 2
#endif
typedef struct { float x, y, z; } Vec3;
typedef struct { float x, y; } Vec2;
typedef void *(*ResolveIcall)(const char *);
typedef void (*PositionFn)(Vec3 *);
typedef void (*ScrollFn)(Vec2 *);
typedef bool (*ButtonFn)(int);
typedef void (*UpdateFn)(void *, const void *);
typedef int (*IntFn)(void);
static Shared *g;
/* Keep a handle as well as the view so the named object remains discoverable
 * when a controller disconnects and another controller reconnects later. */
static HANDLE mapping_handle;
static PositionFn original_position;
static ScrollFn original_scroll;
static ButtonFn original_down, original_up, original_held;
static UpdateFn original_update;
static IntFn frame_count, screen_width, screen_height;
static size_t focus_offset;
static size_t input_module_offset;
static void *(*object_class)(void *);
static const char *(*class_name)(void *);
static const char *(*class_namespace)(void *);
static void *(*class_parent)(void *);
static int cached_frame = -1;
static uint32_t cached_session;
static LONG command_seq;
static int held, down, up, wheel;
static bool active;
static Vec3 position;
static SRWLOCK state_lock = SRWLOCK_INIT;
#ifdef MONO_BACKEND
static uint32_t held_keys[16], down_keys[16], up_keys[16];
#endif

static bool lease_valid(void) {
    return g && g->magic == 0x314d5449 && g->version == IPC_VERSION && g->status == 2 && g->enabled &&
           g->owner_pid && GetTickCount64() - g->heartbeat < 1200;
}

/* Called on Unity's own update/input threads. Cache transitions for one frame
 * so every consumer sees the same Down/Up, even if queried more than once. */
static void snapshot(void) {
    int frame = frame_count();
    AcquireSRWLockExclusive(&state_lock);
    if (frame == cached_frame) {
        ReleaseSRWLockExclusive(&state_lock);
        return;
    }
    cached_frame = frame;
    InterlockedExchange(&g->frame, frame);
    bool valid = lease_valid();
    int previous = held;
#ifdef MONO_BACKEND
    uint32_t desired_keys[16];
    memcpy(desired_keys, held_keys, sizeof(desired_keys));
#endif
    if (valid) {
        LONG seq = g->seq;
        if (!(seq & 1)) {
            MemoryBarrier();
            LONG x = g->x, y = g->y, desired = g->buttons, requested_wheel = g->wheel;
            uint32_t session = g->session;
#ifdef MONO_BACKEND
            uint32_t requested_keys[16];
            memcpy(requested_keys, g->keys, sizeof(requested_keys));
#endif
            MemoryBarrier();
            if (seq == g->seq) {
                if (session != cached_session) {
                    cached_session = session;
                    previous = held = 0;
                    command_seq = -1;
                }
                RECT client;
#ifdef MONO_BACKEND
                client.right = g->client_width;
                client.bottom = g->client_height;
                memcpy(desired_keys, requested_keys, sizeof(desired_keys));
                if (client.right > 0 && client.bottom > 0) {
                    g->render_width = screen_width();
                    g->render_height = screen_height();
#else
                if (GetClientRect((HWND)(uintptr_t)g->hwnd, &client) && client.right > 0 && client.bottom > 0) {
#endif
                    position.x = (float)x * screen_width() / client.right;
                    position.y = (float)screen_height() - (float)y * screen_height() / client.bottom;
                    position.z = 0;
                    held = desired & 7;
                    wheel = seq != command_seq ? requested_wheel : 0;
                    command_seq = seq;
                } else {
                    valid = false;
                    held = 0;
                }
            }
        }
    } else {
        held = 0;
        wheel = 0;
    }
    down = held & ~previous;
    up = previous & ~held;
#ifdef MONO_BACKEND
    bool key_release = false;
    for (int i = 0; i < 16; ++i) {
        uint32_t next = valid ? desired_keys[i] : 0;
        down_keys[i] = next & ~held_keys[i];
        up_keys[i] = held_keys[i] & ~next;
        held_keys[i] = next;
        key_release |= up_keys[i] != 0;
    }
#endif
    /* One virtual release frame on a lost heartbeat prevents stuck UI drags. */
    active = valid || up != 0;
#ifdef MONO_BACKEND
    active |= key_release;
#endif
    InterlockedExchange(&g->native_session, (LONG)cached_session);
    ReleaseSRWLockExclusive(&state_lock);
}

static void virtual_position(Vec3 *out) {
    snapshot();
    AcquireSRWLockShared(&state_lock);
    bool use_virtual = active;
    if (use_virtual) *out = position;
    ReleaseSRWLockShared(&state_lock);
    if (use_virtual) InterlockedIncrement(&g->position_reads);
    else original_position(out);
}
static bool virtual_down(int button) {
    snapshot();
    AcquireSRWLockShared(&state_lock);
    bool use_virtual = active && button >= 0 && button <= 2;
    bool result = use_virtual && (down & (1 << button)) != 0;
    ReleaseSRWLockShared(&state_lock);
    if (!use_virtual) return original_down(button);
    InterlockedIncrement(&g->button_reads);
    return result;
}
static bool virtual_up(int button) {
    snapshot();
    AcquireSRWLockShared(&state_lock);
    bool use_virtual = active && button >= 0 && button <= 2;
    bool result = use_virtual && (up & (1 << button)) != 0;
    ReleaseSRWLockShared(&state_lock);
    if (!use_virtual) return original_up(button);
    InterlockedIncrement(&g->button_reads);
    return result;
}
static bool virtual_held(int button) {
    snapshot();
    AcquireSRWLockShared(&state_lock);
    bool use_virtual = active && button >= 0 && button <= 2;
    bool result = use_virtual && (held & (1 << button)) != 0;
    ReleaseSRWLockShared(&state_lock);
    if (!use_virtual) return original_held(button);
    InterlockedIncrement(&g->button_reads);
    return result;
}
static void virtual_scroll(Vec2 *out) {
    snapshot();
    AcquireSRWLockShared(&state_lock);
    bool use_virtual = active;
    if (use_virtual) { out->x = 0; out->y = (float)wheel; }
    ReleaseSRWLockShared(&state_lock);
    if (!use_virtual) original_scroll(out);
}
static void virtual_update(void *instance, const void *method) {
    if (lease_valid() && input_module_offset) {
        void *module = *(void **)((unsigned char *)instance + input_module_offset);
        if (module) {
            void *klass = object_class(module);
            for (int depth = 0; klass && depth < 32; depth++, klass = class_parent(klass)) {
                const char *name = class_name(klass), *space = class_namespace(klass);
                if ((name && !strcmp(name, "InputSystemUIInputModule")) ||
                    (space && !strncmp(space, "UnityEngine.InputSystem", 23))) {
                    InterlockedExchange(&g->status, -9);
                    break;
                }
            }
        }
    }
    snapshot();
    InterlockedIncrement(&g->updates);
    AcquireSRWLockShared(&state_lock);
    bool use_virtual = active;
    LONG seq = command_seq;
    ReleaseSRWLockShared(&state_lock);
    if (use_virtual) {
        /* Only this EventSystem's focus value, only for its update. This does
         * not send activation messages or change the OS foreground window. */
        bool *focus = (bool *)((unsigned char *)instance + focus_offset);
        bool saved = *focus;
        *focus = true;
        if (!saved) InterlockedIncrement(&g->focus_overrides);
        original_update(instance, method);
        *focus = saved;
        InterlockedExchange(&g->ack, seq);
    } else original_update(instance, method);
}

static bool install(void *target, void *replacement, void **original) {
    return target && MH_CreateHook(target, replacement, original) == MH_OK;
}

static bool executable_in_module(void *pointer, HMODULE module) {
    MEMORY_BASIC_INFORMATION info;
    if (!pointer || VirtualQuery(pointer, &info, sizeof(info)) != sizeof(info)) return false;
    DWORD protection = info.Protect & 0xff;
    return info.State == MEM_COMMIT && info.AllocationBase == (void *)module &&
           !(info.Protect & PAGE_GUARD) && (protection == PAGE_EXECUTE || protection == PAGE_EXECUTE_READ ||
           protection == PAGE_EXECUTE_READWRITE || protection == PAGE_EXECUTE_WRITECOPY);
}

#ifdef MONO_BACKEND
#include "mono_runtime.h"
#else
static DWORD WINAPI initialize(void *unused) {
    (void)unused;
    wchar_t mapping[96];
    wsprintfW(mapping, L"Local\\ITMUnityProfiles_%lu", GetCurrentProcessId());
    HANDLE handle = OpenFileMappingW(FILE_MAP_ALL_ACCESS, FALSE, mapping);
    if (!handle) return 1;
    g = (Shared *)MapViewOfFile(handle, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(Shared));
    if (!g) { CloseHandle(handle); return 2; }
    mapping_handle = handle;
    if (g->magic != 0x314d5449 || g->version != 2) return 3;
    g->status = 1;
    HMODULE assembly = GetModuleHandleW(L"GameAssembly.dll");
    if (!assembly) { g->status = -1; return 4; }

#define API(type, name) type name = (type)(void *)GetProcAddress(assembly, "il2cpp_" #name)
    typedef void *(*NoArg)(void);
    typedef void *(*Attach)(void *);
    typedef void (*Detach)(void *);
    typedef const void **(*Assemblies)(void *, size_t *);
    typedef const void *(*Image)(const void *);
    typedef const char *(*ImageName)(const void *);
    typedef void *(*Class)(const void *, const char *, const char *);
    typedef const void *(*Method)(void *, const char *, int);
    typedef void *(*Field)(void *, const char *);
    typedef size_t (*Offset)(void *);
    typedef void *(*FieldType)(void *);
    typedef int (*TypeKind)(void *);
    typedef uint32_t (*InstanceSize)(void *);
    typedef void *(*ObjectClass)(void *);
    typedef const char *(*ClassName)(void *);
    API(NoArg, domain_get);
    API(Attach, thread_attach);
    API(Detach, thread_detach);
    API(Assemblies, domain_get_assemblies);
    API(Image, assembly_get_image);
    API(ImageName, image_get_name);
    API(Class, class_from_name);
    API(Method, class_get_method_from_name);
    API(Field, class_get_field_from_name);
    API(Offset, field_get_offset);
    API(FieldType, field_get_type);
    API(TypeKind, type_get_type);
    API(InstanceSize, class_instance_size);
    API(ObjectClass, object_get_class);
    API(ClassName, class_get_name);
    API(ClassName, class_get_namespace);
    API(ObjectClass, class_get_parent);
    API(ResolveIcall, resolve_icall);
    if (!domain_get || !thread_attach || !thread_detach || !domain_get_assemblies ||
        !assembly_get_image || !image_get_name || !class_from_name ||
        !class_get_method_from_name || !class_get_field_from_name || !field_get_offset ||
        !field_get_type || !type_get_type || !class_instance_size || !resolve_icall ||
        !object_get_class || !class_get_name || !class_get_namespace || !class_get_parent) {
        g->status = -2; return 5;
    }
    void *domain = domain_get();
    if (!domain) { g->status = -3; return 6; }
    void *thread = thread_attach(domain);
    if (!thread) { g->status = -3; return 6; }
    size_t count = 0;
    const void **assemblies = domain_get_assemblies(domain, &count);
    void *event_class = NULL;
    for (size_t i = 0; i < count; ++i) {
        const void *image = assembly_get_image(assemblies[i]);
        const char *name = image_get_name(image);
        if (name && (!strcmp(name, "UnityEngine.UI.dll") || !strcmp(name, "UnityEngine.UI"))) {
            event_class = class_from_name(image, "UnityEngine.EventSystems", "EventSystem");
            break;
        }
    }
    const void *update_method = event_class ? class_get_method_from_name(event_class, "Update", 0) : NULL;
    void *focus_field = event_class ? class_get_field_from_name(event_class, "m_HasFocus") : NULL;
    focus_offset = focus_field ? field_get_offset(focus_field) : 0;
    void *update = update_method ? *(void * const *)update_method : NULL;
    bool field_valid = focus_field && type_get_type(field_get_type(focus_field)) == 0x02 &&
                       focus_offset >= 16 && focus_offset < class_instance_size(event_class);
    void *module_field = event_class ? class_get_field_from_name(event_class, "m_CurrentInputModule") : NULL;
    input_module_offset = module_field ? field_get_offset(module_field) : 0;
    if (!module_field || input_module_offset < 16 ||
        input_module_offset + sizeof(void *) > class_instance_size(event_class) ||
        type_get_type(field_get_type(module_field)) != 0x12) field_valid = false;
    object_class = object_get_class;
    class_name = class_get_name;
    class_namespace = class_get_namespace;
    class_parent = class_get_parent;
    frame_count = (IntFn)resolve_icall("UnityEngine.Time::get_frameCount()");
    screen_width = (IntFn)resolve_icall("UnityEngine.Screen::get_width()");
    screen_height = (IntFn)resolve_icall("UnityEngine.Screen::get_height()");
    void *pos = resolve_icall("UnityEngine.Input::get_mousePosition_Injected(UnityEngine.Vector3&)");
    void *d = resolve_icall("UnityEngine.Input::GetMouseButtonDown(System.Int32)");
    void *u = resolve_icall("UnityEngine.Input::GetMouseButtonUp(System.Int32)");
    void *h = resolve_icall("UnityEngine.Input::GetMouseButton(System.Int32)");
    void *s = resolve_icall("UnityEngine.Input::get_mouseScrollDelta_Injected(UnityEngine.Vector2&)");
    thread_detach(thread);
    if (!update || focus_offset < 16 || focus_offset > 1024 || !frame_count || !screen_width || !screen_height || !pos || !d || !u || !h || !s) {
        g->status = -4; return 7;
    }
    HMODULE player = GetModuleHandleW(L"UnityPlayer.dll");
    if (!player || !field_valid || !executable_in_module(update, assembly) ||
        !executable_in_module(pos, player) || !executable_in_module(d, player) ||
        !executable_in_module(u, player) || !executable_in_module(h, player) ||
        !executable_in_module(s, player) || !executable_in_module((void *)frame_count, player) ||
        !executable_in_module((void *)screen_width, player) || !executable_in_module((void *)screen_height, player)) {
        g->status = -8; return 11;
    }
    MH_STATUS result = MH_Initialize();
    if (result != MH_OK) { g->error_code = result; g->status = -5; return 8; }
    if (!install(pos, virtual_position, (void **)&original_position) ||
        !install(d, virtual_down, (void **)&original_down) ||
        !install(u, virtual_up, (void **)&original_up) ||
        !install(h, virtual_held, (void **)&original_held) ||
        !install(s, virtual_scroll, (void **)&original_scroll) ||
        !install(update, virtual_update, (void **)&original_update)) {
        MH_Uninitialize(); g->status = -6; return 9;
    }
    result = MH_EnableHook(MH_ALL_HOOKS);
    if (result != MH_OK) {
        MH_DisableHook(MH_ALL_HOOKS); MH_Uninitialize();
        g->error_code = result; g->status = -7; return 10;
    }
    InterlockedExchange(&g->status, 2);
    return 0;
}
#endif

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        HANDLE worker = CreateThread(NULL, 0, initialize, NULL, 0, NULL);
        if (worker) CloseHandle(worker);
    }
    return TRUE;
}
