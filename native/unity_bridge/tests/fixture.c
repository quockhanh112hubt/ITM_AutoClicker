/* A hidden, disposable fake Unity runtime. Never uses the real game. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <stddef.h>

#ifdef FIXTURE_MAIN
int main(void) {
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
#else
typedef struct { float x, y, z; } Vec3;
typedef struct { float x, y; } Vec2;
typedef struct { char padding[16]; bool focused; } Event;
typedef struct { volatile LONG frames, down, up, focus_updates; float x, y; LONG held; } Observer;
static Event event;
static Observer *observer;
static volatile int frame, dummy;
#define EXPORT __declspec(dllexport)
#define NOINLINE __declspec(noinline)
NOINLINE static int get_frame(void) { return frame; }
NOINLINE static int get_width(void) { return 1280 + dummy; }
NOINLINE static int get_height(void) { return 720 + dummy; }
NOINLINE static void pos(Vec3 *p) { p->x = 111 + dummy; p->y = 222 + dummy; p->z = dummy; }
NOINLINE static void scroll(Vec2 *p) { p->x = dummy; p->y = dummy; }
NOINLINE static bool btn_down(int b) { return dummy == b + 99; }
NOINLINE static bool btn_up(int b) { return dummy == b + 98; }
NOINLINE static bool btn_held(int b) { return dummy == b + 97; }
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
    (void)klass;return !strcmp(name,"m_HasFocus") ? &event : NULL;
}
EXPORT size_t il2cpp_field_get_offset(void *field) { (void)field;return offsetof(Event,focused); }
EXPORT void *il2cpp_resolve_icall(const char *name) {
    if (strstr(name,"get_mousePosition_Injected")) return pos;
    if (strstr(name,"get_mouseScrollDelta_Injected")) return scroll;
    if (strstr(name,"GetMouseButtonDown")) return btn_down;
    if (strstr(name,"GetMouseButtonUp")) return btn_up;
    if (strstr(name,"GetMouseButton(")) return btn_held;
    if (strstr(name,"get_frameCount")) return get_frame;
    if (strstr(name,"Screen::get_width")) return get_width;
    if (strstr(name,"Screen::get_height")) return get_height;
    return NULL;
}
EXPORT void fixture_tick(void) {
    if (!observer) {
        wchar_t name[96]; wsprintfW(name,L"Local\\ITMUnityFixture_%lu",GetCurrentProcessId());
        HANDLE h=CreateFileMappingW(INVALID_HANDLE_VALUE,NULL,PAGE_READWRITE,0,sizeof(Observer),name);
        /* Intentionally retain the named object's handle for this process. */
        if (h) observer=MapViewOfFile(h,FILE_MAP_ALL_ACCESS,0,0,sizeof(Observer));
    }
    frame++;
    if (observer) observer->frames=frame;
    update(&event,NULL);
}
#endif
