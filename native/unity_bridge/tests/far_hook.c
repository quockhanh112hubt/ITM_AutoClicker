/* Regression: execute the x64 absolute JIT detour, never touches a real game. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "MinHook.h"

typedef int64_t (*Fn)(int64_t);
static Fn original, target;
static volatile LONG stop, errors;
static int64_t detour(int64_t n) { return original(n) + 100; }
static DWORD WINAPI caller(void *unused) {
    (void)unused;
    while (!stop) {
        int64_t n = target(5);
        if (n != 6 && n != 106) InterlockedIncrement(&errors);
    }
    return 0;
}
#define CHECK(condition) do { if (!(condition)) { printf("FAIL line %d\n", __LINE__); return 1; } } while (0)
int main(void) {
    /* push rbp; mov rbp,rsp; sub rsp,32; mov [rbp-8],rcx;
       mov rax,[rbp-8]; add rax,1; leave; ret */
    const unsigned char prologue[] = {0x55,0x48,0x89,0xe5,0x48,0x83,0xec,0x20,
        0x48,0x89,0x4d,0xf8,0x48,0x8b,0x45,0xf8,0x48,0x83,0xc0,0x01,0xc9,0xc3};
    unsigned char *code = VirtualAlloc(NULL,4096,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    CHECK(code);
    memcpy(code,prologue,sizeof(prologue));
    /* A RIP-relative load must be rejected by the conservative far path. */
    unsigned char rip[] = {0x48,0x8b,0x05,0,0,0,0,0xc3};
    memcpy(code+64,rip,sizeof(rip));
    code[128]=0xc3;
    FlushInstructionCache(GetCurrentProcess(),code,4096);
    target=(Fn)code;
    CHECK(MH_Initialize()==MH_OK);
    CHECK(MH_CreateHookFar(code,detour,(void **)&original)==MH_OK);
    CHECK(target(5)==6 && original(5)==6);
    CHECK(MH_EnableHook(code)==MH_OK);
    CHECK(target(5)==106 && original(5)==6);
    CHECK(MH_DisableHook(code)==MH_OK);
    CHECK(target(5)==6 && !memcmp(code,prologue,sizeof(prologue)));
    HANDLE thread=CreateThread(NULL,0,caller,NULL,0,NULL);
    CHECK(thread);
    for (int i=0;i<150;++i) {
        CHECK(MH_EnableHook(code)==MH_OK);
        CHECK(MH_DisableHook(code)==MH_OK);
    }
    InterlockedExchange(&stop,1);
    CHECK(WaitForSingleObject(thread,5000)==WAIT_OBJECT_0);
    CloseHandle(thread);
    CHECK(errors==0);
    CHECK(MH_RemoveHook(code)==MH_OK);
    CHECK(MH_CreateHookFar(code+64,detour,NULL)==MH_ERROR_UNSUPPORTED_FUNCTION);
    CHECK(MH_CreateHookFar(code+128,detour,NULL)==MH_ERROR_UNSUPPORTED_FUNCTION);
    CHECK(!memcmp(code+64,rip,sizeof(rip)) && code[128]==0xc3);
    CHECK(MH_CreateHookFar(code,detour,(void **)&original)==MH_OK);
    CHECK(MH_EnableHook(code)==MH_OK && target(5)==106);
    CHECK(MH_Uninitialize()==MH_OK && target(5)==6);
    CHECK(!memcmp(code,prologue,sizeof(prologue)));
    VirtualFree(code,0,MEM_RELEASE);
    puts("Absolute JIT hook: trampoline execution, repeated thread suspension, restore/remove/uninitialize, RIP/short-prologue rejection: OK");
    return 0;
}
