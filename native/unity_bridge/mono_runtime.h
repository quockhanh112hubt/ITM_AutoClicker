/* Mono runtime adapter. Included by bridge.c only with MONO_BACKEND.
 * All addresses/field offsets come from the running runtime, never a game RVA.
 */
typedef void *(*MonoMethod)(void *, const char *, int);
typedef void *(*MonoClass)(void *, const char *, const char *);
static void *(*mono_image)(void *);
static const char *(*mono_image_name)(void *);
static MonoClass mono_class;
static MonoMethod mono_method;
static void *(*mono_icall)(void *);
static void *ui_class, *input_class, *time_class, *screen_class;
static ButtonFn original_key_down, original_key_up, original_key_held;

static bool virtual_key(int key, int kind) {
    snapshot();
    AcquireSRWLockShared(&state_lock);
    bool use_virtual = active && key >= 0 && key < 512;
    const uint32_t *bits = kind == 1 ? down_keys : kind == 2 ? up_keys : held_keys;
    bool result = use_virtual && (bits[key / 32] & (1u << (key % 32))) != 0;
    ReleaseSRWLockShared(&state_lock);
    if (use_virtual) { InterlockedIncrement(&g->key_reads); return result; }
    return (kind == 1 ? original_key_down : kind == 2 ? original_key_up : original_key_held)(key);
}
static bool virtual_key_down(int key) { return virtual_key(key, 1); }
static bool virtual_key_up(int key) { return virtual_key(key, 2); }
static bool virtual_key_held(int key) { return virtual_key(key, 0); }

static void collect_assembly(void *assembly, void *unused) {
    (void)unused;
    void *image = mono_image(assembly);
    const char *name = mono_image_name(image);
    if (!name) return;
    if (!strcmp(name, "UnityEngine.UI") || !strcmp(name, "UnityEngine.UI.dll"))
        ui_class = mono_class(image, "UnityEngine.EventSystems", "EventSystem");
    if (!strcmp(name, "UnityEngine.InputLegacyModule") || !strcmp(name, "UnityEngine.InputLegacyModule.dll"))
        input_class = mono_class(image, "UnityEngine", "Input");
    if (!strcmp(name, "UnityEngine.CoreModule") || !strcmp(name, "UnityEngine.CoreModule.dll")) {
        time_class = mono_class(image, "UnityEngine", "Time");
        screen_class = mono_class(image, "UnityEngine", "Screen");
    }
}
static void *lookup(void *klass, const char *name, int argc) {
    void *method = klass ? mono_method(klass, name, argc) : NULL;
    return method ? mono_icall(method) : NULL;
}
static bool executable_jit(void *pointer) {
    MEMORY_BASIC_INFORMATION info;
    if (!pointer || VirtualQuery(pointer, &info, sizeof(info)) != sizeof(info)) return false;
    DWORD p = info.Protect & 0xff;
    return info.State == MEM_COMMIT && !(info.Protect & PAGE_GUARD) &&
        (p == PAGE_EXECUTE || p == PAGE_EXECUTE_READ || p == PAGE_EXECUTE_READWRITE || p == PAGE_EXECUTE_WRITECOPY);
}
static DWORD WINAPI initialize(void *unused) {
    (void)unused;
    wchar_t mapping[96];
    wsprintfW(mapping, L"Local\\ITMUnityMono_v1_%lu", GetCurrentProcessId());
    HANDLE handle = OpenFileMappingW(FILE_MAP_ALL_ACCESS, FALSE, mapping);
    if (!handle) return 1;
    g = (Shared *)MapViewOfFile(handle, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(Shared));
    if (!g) { CloseHandle(handle); return 2; }
    mapping_handle = handle;
    if (g->magic != 0x314d5449 || g->version != IPC_VERSION) return 3;
    g->status = 1;
    HMODULE runtime = GetModuleHandleW(L"mono-2.0-bdwgc.dll");
    if (!runtime) { g->status = -1; return 4; }
    #define MONO(type, name) type name = (type)(void *)GetProcAddress(runtime, "mono_" #name)
    typedef void *(*NoArg)(void);
    typedef void *(*Unary)(void *);
    typedef void (*Detach)(void *);
    typedef void (*Each)(void (*)(void *, void *), void *);
    typedef void *(*Field)(void *, const char *);
    typedef int (*Offset)(void *);
    typedef int (*Type)(void *);
    typedef uint32_t (*Size)(void *, uint32_t *);
    typedef const char *(*Name)(void *);
    MONO(NoArg, get_root_domain); MONO(Unary, thread_attach); MONO(Detach, thread_detach);
    MONO(Each, assembly_foreach); MONO(Unary, assembly_get_image); MONO(Name, image_get_name);
    MONO(MonoClass, class_from_name); MONO(MonoMethod, class_get_method_from_name);
    MONO(Unary, lookup_internal_call); MONO(Unary, compile_method);
    MONO(Field, class_get_field_from_name); MONO(Offset, field_get_offset);
    MONO(Unary, field_get_type); MONO(Type, type_get_type); MONO(Size, class_instance_size);
    MONO(Unary, object_get_class); MONO(Name, class_get_name); MONO(Name, class_get_namespace); MONO(Unary, class_get_parent);
    if (!get_root_domain || !thread_attach || !thread_detach || !assembly_foreach || !assembly_get_image ||
        !image_get_name || !class_from_name || !class_get_method_from_name || !lookup_internal_call || !compile_method ||
        !class_get_field_from_name || !field_get_offset || !field_get_type || !type_get_type || !class_instance_size ||
        !object_get_class || !class_get_name || !class_get_namespace || !class_get_parent) { g->status = -2; return 5; }
    void *domain = get_root_domain();
    void *thread = domain ? thread_attach(domain) : NULL;
    if (!thread) { g->status = -3; return 6; }
    mono_image = assembly_get_image; mono_image_name = image_get_name;
    mono_class = class_from_name; mono_method = class_get_method_from_name; mono_icall = lookup_internal_call;
    assembly_foreach(collect_assembly, NULL);
    void *method = ui_class ? mono_method(ui_class, "Update", 0) : NULL;
    void *update = method ? compile_method(method) : NULL;
    void *focus = ui_class ? class_get_field_from_name(ui_class, "m_HasFocus") : NULL;
    void *module = ui_class ? class_get_field_from_name(ui_class, "m_CurrentInputModule") : NULL;
    focus_offset = focus ? field_get_offset(focus) : 0;
    input_module_offset = module ? field_get_offset(module) : 0;
    uint32_t align = 0, size = ui_class ? class_instance_size(ui_class, &align) : 0;
    bool field_valid = focus && module && focus_offset >= 16 && focus_offset < size &&
        input_module_offset >= 16 && input_module_offset + sizeof(void *) <= size &&
        type_get_type(field_get_type(focus)) == 0x02 && type_get_type(field_get_type(module)) == 0x12;
    object_class = object_get_class; class_name = class_get_name; class_namespace = class_get_namespace; class_parent = class_get_parent;
    frame_count = (IntFn)lookup(time_class, "get_frameCount", 0);
    screen_width = (IntFn)lookup(screen_class, "get_width", 0);
    screen_height = (IntFn)lookup(screen_class, "get_height", 0);
    void *targets[] = {
        lookup(input_class, "get_mousePosition_Injected", 1), lookup(input_class, "GetMouseButtonDown", 1),
        lookup(input_class, "GetMouseButtonUp", 1), lookup(input_class, "GetMouseButton", 1),
        lookup(input_class, "get_mouseScrollDelta_Injected", 1),
        lookup(input_class, "GetKeyDownInt", 1), lookup(input_class, "GetKeyUpInt", 1), lookup(input_class, "GetKeyInt", 1)
    };
    thread_detach(thread);
    HMODULE player = GetModuleHandleW(L"UnityPlayer.dll");
    if (!update || !field_valid || !player || !executable_jit(update)) { g->status = -4; return 7; }
    if (!executable_in_module((void *)frame_count, player) || !executable_in_module((void *)screen_width, player) ||
        !executable_in_module((void *)screen_height, player)) { g->status = -8; return 8; }
    for (int i = 0; i < 8; ++i) if (!executable_in_module(targets[i], player)) { g->error_code = i; g->status = -8; return 8; }
    MH_STATUS result = MH_Initialize();
    if (result != MH_OK) { g->error_code = result; g->status = -5; return 9; }
    void *hooks[] = {virtual_position, virtual_down, virtual_up, virtual_held, virtual_scroll,
                    virtual_key_down, virtual_key_up, virtual_key_held};
    void **originals[] = {(void **)&original_position, (void **)&original_down, (void **)&original_up,
        (void **)&original_held, (void **)&original_scroll, (void **)&original_key_down, (void **)&original_key_up, (void **)&original_key_held};
    bool ok = true;
    for (int i = 0; i < 8 && ok; ++i) ok = install(targets[i], hooks[i], originals[i]);
    if (!ok || !install(update, virtual_update, (void **)&original_update)) {
        MH_Uninitialize(); g->status = -6; return 10;
    }
    result = MH_EnableHook(MH_ALL_HOOKS);
    if (result != MH_OK) { MH_DisableHook(MH_ALL_HOOKS); MH_Uninitialize(); g->error_code = result; g->status = -7; return 11; }
    InterlockedExchange(&g->status, 2);
    return 0;
}
