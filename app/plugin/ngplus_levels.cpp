// NG+ Levels — a Middle-earth Mod Loader plugin for Shadow of War (research build: the scout).
//
// The game computes an orc's shown level when the orc comes into the world (experiment 65: an orc already in the save
// coming by an ambush passes there too; the orcs only seen in the army menu do not):
//     ShadowOfWar.exe+2CDA85 (current Steam exe):  E8 <call> | 41 8B 8F B8 04 00 00  mov ecx,[r15+4B8]  (level - 1)
// The place is the one of the «Adjust uruk level» script of the SeiKur0 Cheat Engine table. This build only records
// the orc structure (r15) of every orc passing there into NGPlusLevels.log next to the plugin, to find where the orc's
// number lies in it — the number the NG+ tool knows from the save. The levels are not changed yet.
//
// The hook as Cheat Engine makes one: the 7 bytes of the mov become a jump to a cave allocated near the exe; the cave
// does the mov itself, stores r15 and counts the passes, and jumps back. A thread reads what the cave stored.
#define WIN32_LEAN_AND_MEAN
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <set>
#include <thread>
#include <atomic>

namespace ModLoader
{
    // the vtable layout of the Mod Loader's LogAPI (modloaderapi.h): Log, LogError
    class LogAPI
    {
    public:
        virtual void Log(const char* fmt, ...) = 0;
        virtual void LogError(const char* fmt, ...) = 0;
    };
    class PluginAPI;
}
#define MODLOADERAPI extern "C" __declspec(dllexport) void

static ModLoader::LogAPI* g_log = nullptr;
static std::atomic<bool> g_run{false};
static uint8_t* g_site = nullptr;                 // the mov [r15+4B8] the jump replaces
static uint8_t g_saved[7];
static uint8_t* g_cave = nullptr;
static volatile uint64_t* g_last = nullptr;       // in the cave: the last orc structure
static volatile uint32_t* g_count = nullptr;      // in the cave: passes
static char g_logPath[MAX_PATH];

// E8 ?? ?? ?? ?? 41 8B 8F B8 04 00 00 4C 8D 45 (-1 = any byte)
static const int SIG[] = {0xE8, -1, -1, -1, -1, 0x41, 0x8B, 0x8F, 0xB8, 0x04, 0x00, 0x00, 0x4C, 0x8D, 0x45};
static const int SIG_LEN = sizeof(SIG) / sizeof(SIG[0]);
static const uint32_t STRUCT_SIZE = 0x700;        // the orc fields known reach +528

static void Log(const char* fmt, ...)
{
    char buf[1024];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (g_log)
        g_log->Log("%s", buf);
    if (FILE* f = fopen(g_logPath, "a"))
    {
        SYSTEMTIME t;
        GetLocalTime(&t);
        fprintf(f, "%02d:%02d:%02d  %s\n", t.wHour, t.wMinute, t.wSecond, buf);
        fclose(f);
    }
}

static uint8_t* Scan()
{
    HMODULE exe = GetModuleHandleW(L"ShadowOfWar.exe");
    if (!exe)
        return nullptr;
    auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(exe);
    auto nt = reinterpret_cast<IMAGE_NT_HEADERS*>(reinterpret_cast<uint8_t*>(exe) + dos->e_lfanew);
    uint8_t* base = reinterpret_cast<uint8_t*>(exe);
    uint8_t* end = base + nt->OptionalHeader.SizeOfImage;
    MEMORY_BASIC_INFORMATION mbi{};
    for (uint8_t* p = base; p < end; p += mbi.RegionSize)
    {
        if (!VirtualQuery(p, &mbi, sizeof(mbi)))
            break;
        if (mbi.State != MEM_COMMIT || (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)))
            continue;
        uint8_t* r = static_cast<uint8_t*>(mbi.BaseAddress);
        size_t n = mbi.RegionSize;
        for (size_t i = 0; i + SIG_LEN <= n; ++i)
        {
            int k = 0;
            while (k < SIG_LEN && (SIG[k] < 0 || r[i + k] == SIG[k]))
                ++k;
            if (k == SIG_LEN)
                return r + i;
        }
    }
    return nullptr;
}

static uint8_t* AllocNear(uint8_t* at)
{
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    uintptr_t step = si.dwAllocationGranularity;
    uintptr_t from = (reinterpret_cast<uintptr_t>(at) & ~(step - 1));
    for (uintptr_t d = step; d < 0x70000000; d += step)
        for (int s = -1; s <= 1; s += 2)
        {
            uintptr_t a = s < 0 ? from - d : from + d;
            if (void* p = VirtualAlloc(reinterpret_cast<void*>(a), 0x1000, MEM_COMMIT | MEM_RESERVE,
                                       PAGE_EXECUTE_READWRITE))
                return static_cast<uint8_t*>(p);
        }
    return nullptr;
}

static void Put32(uint8_t* p, int32_t v) { memcpy(p, &v, 4); }

static bool Hook()
{
    uint8_t* hit = Scan();
    if (!hit)
        return false;
    g_site = hit + 5;
    g_cave = AllocNear(g_site);
    if (!g_cave)
    {
        Log("no memory near the exe for the cave");
        return true;                              // found, but nothing to do: stop searching
    }
    uint8_t* back = g_site + 7;
    uint8_t* c = g_cave;
    uint8_t* data = g_cave + 0x100;               // last (8), count (4)
    g_last = reinterpret_cast<volatile uint64_t*>(data);
    g_count = reinterpret_cast<volatile uint32_t*>(data + 8);
    // mov ecx,[r15+4B8]
    memcpy(c, g_site, 7); c += 7;
    // mov [rip+last],r15
    c[0] = 0x4C; c[1] = 0x89; c[2] = 0x3D; Put32(c + 3, int32_t(data - (c + 7))); c += 7;
    // lock inc dword [rip+count]
    c[0] = 0xF0; c[1] = 0xFF; c[2] = 0x05; Put32(c + 3, int32_t(data + 8 - (c + 7))); c += 7;
    // jmp [rip+0] ; dq back
    c[0] = 0xFF; c[1] = 0x25; Put32(c + 2, 0); memcpy(c + 6, &back, 8); c += 14;
    FlushInstructionCache(GetCurrentProcess(), g_cave, c - g_cave);

    memcpy(g_saved, g_site, 7);
    DWORD old;
    VirtualProtect(g_site, 7, PAGE_EXECUTE_READWRITE, &old);
    uint8_t jump[7] = {0xE9, 0, 0, 0, 0, 0x90, 0x90};
    Put32(jump + 1, int32_t(g_cave - (g_site + 5)));
    memcpy(g_site, jump, 7);
    VirtualProtect(g_site, 7, old, &old);
    FlushInstructionCache(GetCurrentProcess(), g_site, 7);
    Log("hook at ShadowOfWar.exe+%llX, cave %p", (unsigned long long)(g_site - 5 -
        reinterpret_cast<uint8_t*>(GetModuleHandleW(L"ShadowOfWar.exe"))), g_cave);
    return true;
}

static void Unhook()
{
    if (!g_site || !g_cave)
        return;
    DWORD old;
    VirtualProtect(g_site, 7, PAGE_EXECUTE_READWRITE, &old);
    memcpy(g_site, g_saved, 7);
    VirtualProtect(g_site, 7, old, &old);
    FlushInstructionCache(GetCurrentProcess(), g_site, 7);
    g_site = nullptr;                             // the cave stays: a thread may still be inside it
}

static bool ReadSafe(const void* from, void* to, size_t n)
{
    SIZE_T got = 0;
    return ReadProcessMemory(GetCurrentProcess(), from, to, n, &got) && got == n;
}

static void Dump(uint64_t orc)
{
    static uint8_t buf[STRUCT_SIZE];
    if (!ReadSafe(reinterpret_cast<void*>(orc), buf, sizeof(buf)))
    {
        Log("orc %llX: cannot read", (unsigned long long)orc);
        return;
    }
    int32_t lvl;
    memcpy(&lvl, buf + 0x4B8, 4);
    Log("orc %llX: level-1 %d", (unsigned long long)orc, lvl);
    if (FILE* f = fopen(g_logPath, "a"))
    {
        for (uint32_t i = 0; i < sizeof(buf); i += 16)
        {
            fprintf(f, "  +%03X ", i);
            for (int k = 0; k < 16; ++k)
                fprintf(f, " %02X", buf[i + k]);
            fprintf(f, "\n");
        }
        fclose(f);
    }
}

static void Run()
{
    while (g_run && !Hook())
        Sleep(500);
    std::set<uint64_t> seen;
    uint32_t count = 0;
    while (g_run && g_count)
    {
        uint32_t now = *g_count;
        if (now != count)
        {
            count = now;
            uint64_t orc = *g_last;
            if (orc && seen.insert(orc).second)
                Dump(orc);
        }
        Sleep(20);
    }
}

MODLOADERAPI OnRegisterLogAPI(ModLoader::LogAPI* api) { g_log = api; }

MODLOADERAPI OnPluginLoad(ModLoader::PluginAPI*)
{
    g_run = true;
    std::thread(Run).detach();
}

MODLOADERAPI OnPluginUnload()
{
    g_run = false;
    Unhook();
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        GetModuleFileNameA(module, g_logPath, MAX_PATH);
        if (char* dot = strrchr(g_logPath, '.'))
            strcpy(dot, ".log");
        DisableThreadLibraryCalls(module);
    }
    return TRUE;
}
