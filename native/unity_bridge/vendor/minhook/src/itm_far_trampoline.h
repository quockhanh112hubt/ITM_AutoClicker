/* ITM extension to MinHook v1.3.4, under the same BSD license.
 * Conservative x64 fallback for Mono JIT code with no nearby allocation slot.
 * Accept only position-independent straight-line prologues. In particular,
 * never copy a RIP-relative access, call, branch or return without relocation.
 */
#include "hde/hde64.h"
static BOOL CreateFarTrampoline(PTRAMPOLINE ct)
{
    UINT length = 0;
    ct->patchAbove = FALSE;
    ct->nIP = 0;
    while (length < sizeof(JMP_ABS))
    {
        hde64s hs;
        LPBYTE instruction = (LPBYTE)ct->pTarget + length;
        MEMORY_BASIC_INFORMATION memory;
        if (!VirtualQuery(instruction, &memory, sizeof(memory)) ||
            memory.State != MEM_COMMIT || (memory.Protect & (PAGE_GUARD | PAGE_NOACCESS)) ||
            (ULONG_PTR)instruction + 15 > (ULONG_PTR)memory.BaseAddress + memory.RegionSize)
            return FALSE;
        hde64_disasm(instruction, &hs);
        if (!hs.len || (hs.flags & (F_ERROR | F_RELATIVE)) ||
            (hs.modrm & 0xC7) == 0x05 || ct->nIP >= 7)
            return FALSE;
        BOOL push = hs.opcode >= 0x50 && hs.opcode <= 0x57;
        BOOL move = hs.opcode == 0x89 || hs.opcode == 0x8B;
        BOOL stack = (hs.opcode == 0x81 || hs.opcode == 0x83) && hs.modrm == 0xEC;
        if (!push && !move && !stack && hs.opcode != 0x90)
            return FALSE;
        ct->oldIPs[ct->nIP] = ct->newIPs[ct->nIP] = (UINT8)length;
        ct->nIP++;
        memcpy((LPBYTE)ct->pTrampoline + length, instruction, hs.len);
        length += hs.len;
    }
    ct->oldIPs[ct->nIP] = ct->newIPs[ct->nIP] = (UINT8)length;
    ct->nIP++;
    JMP_ABS back = {0xFF, 0x25, 0, (UINT64)((LPBYTE)ct->pTarget + length)};
    memcpy((LPBYTE)ct->pTrampoline + length, &back, sizeof(back));
    ct->pRelay = ct->pDetour;
    FlushInstructionCache(GetCurrentProcess(), ct->pTrampoline, length + sizeof(back));
    return TRUE;
}
