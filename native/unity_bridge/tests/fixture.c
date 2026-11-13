/* A hidden, disposable fake Unity runtime. Never uses the real game. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

#define EXPORT __declspec(dllexport)
#define NOINLINE __declspec(noinline)
typedef struct { float x, y, z; } Vec3;
typedef struct { float x, y; } Vec2;

#ifdef FIXTURE_MAIN
int main(void) {
    if (!LoadLibraryW(L"UnityPlayer.dll")) return 3;
    HMODULE runtime = LoadLibraryW(L"GameAssembly.dll");
    if (!runtime) return 1;
    void (*tick)(void) = (void (*)(void))GetProcAddress(runtime, "fixture_tick");
    HWND window = CreateWindowExW(WS_EX_NOACTIVATE, L"STATIC", L"ITM native fixture", WS_POPUP,
                                  -9000, -9000, 1280, 720, NULL, NULL, NULL, NULL);
    if (!window || !tick) return 2;
    printf("%lu %llu\n", GetCurrentProcessId(), (unsigned long long)(uintptr_t)window);
    fflush(stdout);
    for (;;) { tick(); Sleep(16); }
}
#elif defined(FIXTURE_PLAYER)
static volatile int frame, dummy;
EXPORT NOINLINE int fixture_frame(void) { return frame; }
EXPORT NOINLINE void fixture_next_frame(void) { frame++; }
EXPORT NOINLINE int fixture_width(void) { return 1280 + dummy; }
EXPORT NOINLINE int fixture_height(void) { return 720 + dummy; }
EXPORT NOINLINE void fixture_pos(Vec3 *p) { p->x = 111 + dummy; p->y = 222 + dummy; p->z = dummy; }
EXPORT NOINLINE void fixture_scroll(Vec2 *p) { p->x = dummy; p->y = dummy; }
EXPORT NOINLINE bool fixture_down(int b) { return dummy == b + 99; }
EXPORT NOINLINE bool fixture_up(int b) { return dummy == b + 98; }
EXPORT NOINLINE bool fixture_held(int b) { return dummy == b + 97; }
#else
typedef struct { char padding[16]; bool focused; void *input_module; } Event;
typedef struct { volatile LONG frames, down, up, focus_updates; float x, y; LONG held; } Observer;
static Event event;
static int module_field, module_object;
static int parent_module;
static Observer *observer;
static void (*pos)(Vec3 *);
static bool (*btn_down)(int), (*btn_up)(int), (*btn_held)(int);
static int (*get_frame)(void);
static void (*next_frame)(void);
static void initialize_player(void) {
    HMODULE player=GetModuleHandleW(L"UnityPlayer.dll");
    pos=(void (*)(Vec3 *))(void *)GetProcAddress(player,"fixture_pos");
    btn_down=(bool (*)(int))(void *)GetProcAddress(player,"fixture_down");
    btn_up=(bool (*)(int))(void *)GetProcAddress(player,"fixture_up");
    btn_held=(bool (*)(int))(void *)GetProcAddress(player,"fixture_held");
    get_frame=(int (*)(void))(void *)GetProcAddress(player,"fixture_frame");
    next_frame=(void (*)(void))(void *)GetProcAddress(player,"fixture_next_frame");
}
NOINLINE static void update(void *object, const void *method) {
    (void)method;
    if (!((Event *)object)->focused || !observer) return;
    observer->focus_updates++;
    Vec3 point;
    pos(&point);
    observer->x = point.x; observer->y = point.y;
    if (btn_down(0)) observer->down++;
    if (btn_up(0)) observer->up++;
    observer->held = btn_held(0);
}
static void *method_info[] = {update};
EXPORT void *il2cpp_domain_get(void) { return &event; }
EXPORT void *il2cpp_thread_attach(void *p) { return p; }
EXPORT void il2cpp_thread_detach(void *p) { (void)p; }
EXPORT const void **il2cpp_domain_get_assemblies(void *domain, size_t *count) {
    static const void *assemblies[] = { &event }; (void)domain;
    *count = 1; return assemblies;
}
EXPORT const void *il2cpp_assembly_get_image(const void *p) { return p; }
EXPORT const char *il2cpp_image_get_name(const void *p) { (void)p; return "UnityEngine.UI.dll"; }
EXPORT void *il2cpp_class_from_name(const void *image, const char *ns, const char *name) {
    (void)image;(void)ns;return !strcmp(name,"EventSystem") ? &event : NULL;
}
EXPORT const void *il2cpp_class_get_method_from_name(void *klass, const char *name, int count) {
    (void)klass;(void)count;return !strcmp(name,"Update") ? method_info : NULL;
}
EXPORT void *il2cpp_class_get_field_from_name(void *klass, const char *name) {
    (void)klass;
    if (!strcmp(name,"m_HasFocus")) return &event;
    if (!strcmp(name,"m_CurrentInputModule")) return &module_field;
    return NULL;
}
EXPORT size_t il2cpp_field_get_offset(void *field) { return field==&module_field ? offsetof(Event,input_module) : offsetof(Event,focused); }
EXPORT void *il2cpp_field_get_type(void *field) { return field; }
EXPORT int il2cpp_type_get_type(void *type) {
    if (type==&module_field) return 0x12;
    return getenv("ITM_FIXTURE_BAD_FIELD") ? 0x08 : 0x02;
}
EXPORT uint32_t il2cpp_class_instance_size(void *klass) { (void)klass;return sizeof(Event); }
EXPORT void *il2cpp_object_get_class(void *obj) { return obj; }
EXPORT const char *il2cpp_class_get_name(void *klass) {
    if (getenv("ITM_FIXTURE_NEW_INPUT_DERIVED")) return klass==&parent_module ? "InputSystemUIInputModule" : "CustomGameInputModule";
    return getenv("ITM_FIXTURE_NEW_INPUT") ? "InputSystemUIInputModule" : "StandaloneInputModule";
}
EXPORT const char *il2cpp_class_get_namespace(void *klass) {
    if (getenv("ITM_FIXTURE_NEW_INPUT_DERIVED")) return klass==&parent_module ? "UnityEngine.InputSystem.UI" : "Custom.Game";
    return getenv("ITM_FIXTURE_NEW_INPUT") ? "UnityEngine.InputSystem.UI" : "UnityEngine.EventSystems";
}
EXPORT void *il2cpp_class_get_parent(void *klass) {
    return getenv("ITM_FIXTURE_NEW_INPUT_DERIVED") && klass!=&parent_module ? &parent_module : NULL;
}
EXPORT void *il2cpp_resolve_icall(const char *name) {
    const char *symbol=NULL;
    if (!strcmp(name,"UnityEngine.Input::get_mousePosition_Injected(UnityEngine.Vector3&)")) symbol="fixture_pos";
    if (!strcmp(name,"UnityEngine.Input::get_mouseScrollDelta_Injected(UnityEngine.Vector2&)")) symbol="fixture_scroll";
    if (!strcmp(name,"UnityEngine.Input::GetMouseButtonDown(System.Int32)")) symbol="fixture_down";
    if (!strcmp(name,"UnityEngine.Input::GetMouseButtonUp(System.Int32)")) symbol="fixture_up";
    if (!strcmp(name,"UnityEngine.Input::GetMouseButton(System.Int32)")) symbol="fixture_held";
    if (strstr(name,"get_frameCount")) symbol="fixture_frame";
    if (strstr(name,"Screen::get_width")) symbol="fixture_width";
    if (strstr(name,"Screen::get_height")) symbol="fixture_height";
    if (symbol) return (void *)GetProcAddress(GetModuleHandleW(L"UnityPlayer.dll"),symbol);
    return NULL;
}
EXPORT void fixture_tick(void) {
    event.input_module=&module_object;
    if (!next_frame) initialize_player();
    if (!observer) {
        wchar_t name[96]; wsprintfW(name,L"Local\\ITMUnityFixture_%lu",GetCurrentProcessId());
        HANDLE h=CreateFileMappingW(INVALID_HANDLE_VALUE,NULL,PAGE_READWRITE,0,sizeof(Observer),name);
        /* Intentionally retain the named object's handle for this process. */
        if (h) observer=MapViewOfFile(h,FILE_MAP_ALL_ACCESS,0,0,sizeof(Observer));
    }
    next_frame();
    if (observer) observer->frames=get_frame();
    update(&event,NULL);
}
#endif
