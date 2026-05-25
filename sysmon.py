#!/usr/bin/env python3
"""
sysmon_hacker.py — Hacker-aesthetic live system dashboard for Arch Linux
Deps: pip install psutil
Controls: q=quit  r=refresh  p=sort by MEM  c=sort by CPU
"""

import curses
import time
import psutil
import platform
import socket
import os
import random
from collections import deque
from datetime import datetime, timedelta

REFRESH       = 2
SPARKLINE_LEN = 30
GLITCH_PROB   = 0.04

# ── correct SYSMON banner ──────────────────────────────────────────────────────

BANNER = [
    " ███████╗██╗   ██╗███████╗███╗   ███╗ ██████╗ ███╗   ██╗",
    " ██╔════╝╚██╗ ██╔╝██╔════╝████╗ ████║██╔═══██╗████╗  ██║",
    " ███████╗ ╚████╔╝ ███████╗██╔████╔██║██║   ██║██╔██╗ ██║",
    " ╚════██║  ╚██╔╝  ╚════██║██║╚██╔╝██║██║   ██║██║╚██╗██║",
    " ███████║   ██║   ███████║██║ ╚═╝ ██║╚██████╔╝██║ ╚████║",
    " ╚══════╝   ╚═╝   ╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝",
]

ARCH_TAG    = ">>  ARCH USES ME BTW  <<"
GLITCH_CHARS = "!@#$%^&*<>?/\\|{}[]~`±§"

# ── color pair index constants ─────────────────────────────────────────────────
# 1=green  2=yellow  3=red  4=cyan  5=footer(blk/grn)
# 6=border(green)  7=magenta  8=blue  9=white  10=banner-gradient

C_GREEN   = 1
C_YELLOW  = 2
C_RED     = 3
C_CYAN    = 4
C_FOOTER  = 5
C_BORDER  = 6
C_MAGENTA = 7
C_BLUE    = 8
C_WHITE   = 9

# ── icons (unicode) ───────────────────────────────────────────────────────────
ICO_CPU   = "⚙"
ICO_MEM   = "▤"
ICO_DISK  = "🖴"
ICO_NET   = "⇅"
ICO_TEMP  = "🌡"
ICO_BATT  = "⚡"
ICO_PROC  = "◈"
ICO_LOAD  = "⌛"
ICO_UP    = "↑"
ICO_DOWN  = "↓"
ICO_GOOD  = "●"
ICO_WARN  = "◆"
ICO_BAD   = "✖"

# ── state ─────────────────────────────────────────────────────────────────────

cpu_history = deque([0.0] * SPARKLINE_LEN, maxlen=SPARKLINE_LEN)
mem_history = deque([0.0] * SPARKLINE_LEN, maxlen=SPARKLINE_LEN)
net_prev    = {}
sort_by     = "cpu"
frame_count = 0

# ── helpers ───────────────────────────────────────────────────────────────────

def bar(value, width=20, filled="▓", empty="░"):
    n = int((value / 100) * width)
    return filled * n + empty * (width - n)

def spark(history, width=20):
    BLOCKS = " ▁▂▃▄▅▆▇█"
    data   = list(history)[-width:]
    return "".join(BLOCKS[min(8, int((v / 100) * 8))] for v in data).rjust(width)

def bytes_to_human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"

def uptime():
    delta = timedelta(seconds=int(time.time() - psutil.boot_time()))
    d, s  = delta.days, delta.seconds
    h, m  = divmod(s, 3600)
    m    //= 60
    return f"{d}d {h}h {m}m" if d else f"{h}h {m}m"

def color_for(pct):
    if pct >= 85: return C_RED
    if pct >= 55: return C_YELLOW
    return C_GREEN

def status_icon(pct):
    if pct >= 85: return ICO_BAD
    if pct >= 55: return ICO_WARN
    return ICO_GOOD

def safe_add(win, row, col, text, attr=0, cols=9999):
    try:
        text = str(text)[:max(0, cols - col - 1)]
        if attr:
            win.attron(attr)
        win.addstr(row, col, text)
        if attr:
            win.attroff(attr)
    except curses.error:
        pass

def hline(win, row, cols, char="═", cp=C_BORDER):
    safe_add(win, row, 0, char * (cols - 1), curses.color_pair(cp))

def box_top(win, row, cols, title="", title_cp=C_CYAN):
    inner = cols - 4
    if title:
        left  = max(0, (inner - len(title) - 2) // 2)
        right = max(0, inner - len(title) - 2 - left)
        line  = "┌─" + "─" * left + "[ " + title + " ]" + "─" * right + "─┐"
    else:
        line = "┌" + "─" * (cols - 2) + "┐"
    line = line[:cols - 1]
    safe_add(win, row, 0, line, curses.color_pair(C_BORDER))
    if title:
        # re-colour just the title text for contrast
        ti  = line.find("[ ") + 2
        safe_add(win, row, ti, title, curses.color_pair(title_cp) | curses.A_BOLD)

def box_bot(win, row, cols):
    safe_add(win, row, 0, ("└" + "─" * (cols - 2) + "┘")[:cols-1],
             curses.color_pair(C_BORDER))

def labeled(win, row, col, label, value, lcp, vcp, cols):
    safe_add(win, row, col, label, curses.color_pair(lcp) | curses.A_BOLD, cols)
    safe_add(win, row, col + len(label), value, curses.color_pair(vcp), cols)

# ── section renderers ─────────────────────────────────────────────────────────

def draw_arch_tag(win, row, cols):
    tag     = ARCH_TAG
    padding = max(0, (cols - len(tag)) // 2)
    line    = " " * padding + tag
    line    = line.ljust(cols - 1)[:cols - 1]
    if random.random() < GLITCH_PROB:
        pos  = random.randint(padding, padding + len(tag) - 1)
        line = line[:pos] + random.choice(GLITCH_CHARS) + line[pos + 1:]
    safe_add(win, row, 0, line,
             curses.color_pair(C_MAGENTA) | curses.A_BOLD | curses.A_BLINK)
    return row + 1

def draw_banner(win, row, cols):
    # Alternate banner lines: cyan / green for two-tone effect
    colors = [C_CYAN, C_GREEN, C_CYAN, C_GREEN, C_CYAN, C_GREEN]
    for i, bline in enumerate(BANNER):
        pad = max(0, (cols - len(bline)) // 2)
        safe_add(win, row, pad, bline,
                 curses.color_pair(colors[i % len(colors)]) | curses.A_BOLD, cols)
        row += 1
    # subtitle
    sub = (f"  {socket.gethostname()}  |  {platform.system()} {platform.release()}"
           f"  |  up {uptime()}  ")
    pad = max(0, (cols - len(sub)) // 2)
    safe_add(win, row, pad, sub, curses.color_pair(C_WHITE), cols)
    return row + 2

def draw_datetime_bar(win, row, cols):
    now   = datetime.now().strftime("  %A %Y-%m-%d  %H:%M:%S")
    loads = os.getloadavg()
    load  = f"  load {loads[0]:.2f} {loads[1]:.2f} {loads[2]:.2f}  "
    gap   = " " * max(0, cols - len(now) - len(load) - 1)
    safe_add(win, row, 0, now,           curses.color_pair(C_CYAN))
    safe_add(win, row, len(now) + len(gap), load, curses.color_pair(C_YELLOW))
    return row + 1

def draw_cpu(win, row, cols):
    global cpu_history
    freq      = psutil.cpu_freq()
    freq_str  = f"{freq.current:.0f}MHz" if freq else "N/A"
    cores     = psutil.cpu_count(logical=False)
    threads   = psutil.cpu_count(logical=True)
    per_cpu   = psutil.cpu_percent(percpu=True)
    total_cpu = sum(per_cpu) / len(per_cpu)
    cpu_history.append(total_cpu)
    cp  = color_for(total_cpu)
    ico = status_icon(total_cpu)

    box_top(win, row, cols,
            f"{ICO_CPU} CPU  {cores}C/{threads}T  {freq_str}", title_cp=C_CYAN)
    row += 1

    # overall bar
    sp = spark(cpu_history, width=SPARKLINE_LEN)
    b  = bar(total_cpu, width=25)
    safe_add(win, row, 2,
             f" {ico} total  ", curses.color_pair(cp) | curses.A_BOLD)
    safe_add(win, row, 13,
             f"[{b}]", curses.color_pair(cp))
    safe_add(win, row, 41,
             f" {total_cpu:5.1f}%  ", curses.color_pair(C_WHITE) | curses.A_BOLD)
    safe_add(win, row, 51,
             f"spark[{sp}]", curses.color_pair(C_BLUE), cols)
    row += 1

    # per-core — 4 per line, label in cyan, bar in usage-color
    chunk = 4
    for i in range(0, len(per_cpu), chunk):
        col = 2
        for j in range(chunk):
            if i + j >= len(per_cpu):
                break
            p   = per_cpu[i + j]
            b2  = bar(p, width=8)
            cp2 = color_for(p)
            label = f"c{i+j:<2} "
            safe_add(win, row, col, label, curses.color_pair(C_CYAN) | curses.A_BOLD)
            col += len(label)
            safe_add(win, row, col, f"[{b2}]", curses.color_pair(cp2))
            col += 11
            safe_add(win, row, col, f"{p:4.0f}%  ", curses.color_pair(C_WHITE))
            col += 8
        row += 1

    box_bot(win, row, cols)
    return row + 1

def draw_memory(win, row, cols):
    global mem_history
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    mem_history.append(vm.percent)

    box_top(win, row, cols, f"{ICO_MEM} MEMORY", title_cp=C_MAGENTA)
    row += 1

    sp = spark(mem_history, width=SPARKLINE_LEN)

    for label, used, total, pct, color in [
        ("RAM ", vm.used, vm.total, vm.percent, C_MAGENTA),
        ("SWAP", sw.used, sw.total, sw.percent, C_BLUE),
    ]:
        cp   = color_for(pct)
        ico  = status_icon(pct)
        b    = bar(pct, width=25)
        info = f"{bytes_to_human(used)}/{bytes_to_human(total)}"
        safe_add(win, row, 2,
                 f" {ico} ", curses.color_pair(cp) | curses.A_BOLD)
        safe_add(win, row, 6,
                 label, curses.color_pair(color) | curses.A_BOLD)
        safe_add(win, row, 11,
                 f"[{b}]", curses.color_pair(cp))
        safe_add(win, row, 39,
                 f" {pct:5.1f}%  {info:<18}", curses.color_pair(C_WHITE))
        if label == "RAM ":
            safe_add(win, row, 39 + 23,
                     f" spark[{sp}]", curses.color_pair(C_BLUE), cols)
        row += 1

    # detail line
    safe_add(win, row, 4,
             f"avail ", curses.color_pair(C_CYAN) | curses.A_BOLD)
    safe_add(win, row, 10,
             bytes_to_human(vm.available), curses.color_pair(C_WHITE))
    safe_add(win, row, 22,
             f"  cached ", curses.color_pair(C_CYAN) | curses.A_BOLD)
    safe_add(win, row, 31,
             bytes_to_human(vm.cached), curses.color_pair(C_WHITE))
    safe_add(win, row, 43,
             f"  buffers ", curses.color_pair(C_CYAN) | curses.A_BOLD)
    safe_add(win, row, 53,
             bytes_to_human(vm.buffers), curses.color_pair(C_WHITE), cols)
    row += 1

    box_bot(win, row, cols)
    return row + 1

def draw_disk(win, row, cols):
    io = psutil.disk_io_counters()
    box_top(win, row, cols, f"{ICO_DISK} DISK", title_cp=C_YELLOW)
    row += 1

    for p in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(p.mountpoint)
        except PermissionError:
            continue
        pct    = usage.percent
        cp     = color_for(pct)
        ico    = status_icon(pct)
        b      = bar(pct, width=15)
        info   = f"{bytes_to_human(usage.used)}/{bytes_to_human(usage.total)}"
        mount  = p.mountpoint[:16].ljust(16)
        fstype = (p.fstype or "?")[:7].ljust(7)
        safe_add(win, row, 2,
                 f" {ico} ", curses.color_pair(cp) | curses.A_BOLD)
        safe_add(win, row, 6,
                 mount, curses.color_pair(C_YELLOW) | curses.A_BOLD)
        safe_add(win, row, 24,
                 fstype, curses.color_pair(C_CYAN))
        safe_add(win, row, 32,
                 f"[{b}]", curses.color_pair(cp))
        safe_add(win, row, 50,
                 f" {pct:5.1f}%  {info}", curses.color_pair(C_WHITE), cols)
        row += 1

    if io:
        safe_add(win, row, 4,
                 f"I/O ", curses.color_pair(C_CYAN) | curses.A_BOLD)
        safe_add(win, row, 8,
                 f"read {bytes_to_human(io.read_bytes)}  "
                 f"write {bytes_to_human(io.write_bytes)}  "
                 f"r_ops {io.read_count}  w_ops {io.write_count}",
                 curses.color_pair(C_WHITE), cols)
        row += 1

    box_bot(win, row, cols)
    return row + 1

def draw_network(win, row, cols):
    global net_prev
    now      = time.time()
    net_io   = psutil.net_io_counters(pernic=True)
    addrs    = psutil.net_if_addrs()
    stats_if = psutil.net_if_stats()

    box_top(win, row, cols, f"{ICO_NET} NETWORK", title_cp=C_BLUE)
    row += 1

    for iface, stats in net_io.items():
        if iface == "lo":
            continue
        ip = "—"
        if iface in addrs:
            for a in addrs[iface]:
                if a.family == socket.AF_INET:
                    ip = a.address
                    break

        up_rate = dn_rate = 0.0
        if iface in net_prev:
            ps, pr, pt = net_prev[iface]
            dt = now - pt
            if dt > 0:
                up_rate = (stats.bytes_sent - ps) / dt
                dn_rate = (stats.bytes_recv - pr) / dt
        net_prev[iface] = (stats.bytes_sent, stats.bytes_recv, now)

        is_up   = stats_if.get(iface, None)
        flag_cp = C_GREEN if (is_up and is_up.isup) else C_RED
        flag    = "UP  " if (is_up and is_up.isup) else "DOWN"

        safe_add(win, row, 2, f" [{flag}] ", curses.color_pair(flag_cp) | curses.A_BOLD)
        safe_add(win, row, 10, iface[:10].ljust(10), curses.color_pair(C_CYAN) | curses.A_BOLD)
        safe_add(win, row, 21, f"IP {ip:<16}", curses.color_pair(C_WHITE))
        safe_add(win, row, 41, f"{ICO_UP}{bytes_to_human(up_rate)}/s", curses.color_pair(C_GREEN))
        safe_add(win, row, 54, f"  {ICO_DOWN}{bytes_to_human(dn_rate)}/s", curses.color_pair(C_YELLOW))
        safe_add(win, row, 68,
                 f"  tot{ICO_UP}{bytes_to_human(stats.bytes_sent)}"
                 f"  tot{ICO_DOWN}{bytes_to_human(stats.bytes_recv)}"
                 f"  err:{stats.errin+stats.errout}"
                 f"  drp:{stats.dropin+stats.dropout}",
                 curses.color_pair(C_WHITE), cols)
        row += 1

    box_bot(win, row, cols)
    return row + 1

def draw_sensors(win, row, cols):
    try:
        temps = psutil.sensors_temperatures()
    except AttributeError:
        return row
    if not temps:
        return row

    box_top(win, row, cols, f"{ICO_TEMP} TEMPERATURES", title_cp=C_RED)
    row += 1
    for chip, entries in temps.items():
        for e in entries:
            if e.current is None:
                continue
            high  = e.high or 85
            crit  = e.critical or 100
            pct   = min(100, (e.current / crit) * 100)
            b     = bar(pct, width=12)
            cp    = 3 if e.current >= high else (2 if e.current >= high * 0.8 else 1)
            ico   = status_icon(pct)
            label = f"{chip}/{e.label or 'temp'}"[:22].ljust(22)
            safe_add(win, row, 2, f" {ico} ", curses.color_pair(cp) | curses.A_BOLD)
            safe_add(win, row, 6, label, curses.color_pair(C_RED))
            safe_add(win, row, 29, f"[{b}]", curses.color_pair(cp))
            safe_add(win, row, 44,
                     f" {e.current:5.1f}°C  high:{high:.0f}°  crit:{crit:.0f}°",
                     curses.color_pair(C_WHITE), cols)
            row += 1
    box_bot(win, row, cols)
    return row + 1

def draw_battery(win, row, cols):
    batt = psutil.sensors_battery()
    if not batt:
        return row

    box_top(win, row, cols, f"{ICO_BATT} BATTERY", title_cp=C_YELLOW)
    row += 1
    status    = "CHARGING [AC]" if batt.power_plugged else "ON BATTERY"
    secs      = batt.secsleft
    time_left = str(timedelta(seconds=int(secs))) if secs > 0 else "calculating"
    cp  = 3 if batt.percent < 20 else (2 if batt.percent < 40 else 1)
    ico = status_icon(batt.percent)
    b   = bar(batt.percent, width=30)
    safe_add(win, row, 2, f" {ico} ", curses.color_pair(cp) | curses.A_BOLD)
    safe_add(win, row, 6, f"[{b}]", curses.color_pair(cp))
    safe_add(win, row, 39,
             f" {batt.percent:.1f}%  ", curses.color_pair(C_WHITE) | curses.A_BOLD)
    safe_add(win, row, 49,
             status, curses.color_pair(C_YELLOW) | curses.A_BOLD)
    safe_add(win, row, 49 + len(status),
             f"  eta {time_left}", curses.color_pair(C_CYAN), cols)
    row += 1
    box_bot(win, row, cols)
    return row + 1

def draw_load_avg(win, row, cols):
    loads = os.getloadavg()
    cores = psutil.cpu_count()
    box_top(win, row, cols, f"{ICO_LOAD} LOAD AVERAGE", title_cp=C_YELLOW)
    row += 1
    for label, val in zip(("1min ","5min ","15min"), loads):
        pct = min(100, (val / cores) * 100)
        b   = bar(pct, width=20)
        cp  = color_for(pct)
        ico = status_icon(pct)
        safe_add(win, row, 2, f" {ico} ", curses.color_pair(cp) | curses.A_BOLD)
        safe_add(win, row, 6, label, curses.color_pair(C_YELLOW) | curses.A_BOLD)
        safe_add(win, row, 12, f"[{b}]", curses.color_pair(cp))
        safe_add(win, row, 35,
                 f" {val:.2f}  ({pct:.0f}% of {cores} cores)",
                 curses.color_pair(C_WHITE), cols)
        row += 1
    box_bot(win, row, cols)
    return row + 1

def draw_processes(win, row, cols, max_procs=10):
    global sort_by
    procs = []
    for p in psutil.process_iter(
            ["pid","name","cpu_percent","memory_percent","status","username","num_threads"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    key       = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    procs     = sorted(procs, key=lambda x: x[key] or 0, reverse=True)[:max_procs]
    sort_lbl  = "CPU ▼" if sort_by == "cpu" else "MEM ▼"

    box_top(win, row, cols,
            f"{ICO_PROC} PROCESSES  sort:{sort_lbl}  [c]cpu [p]mem",
            title_cp=C_GREEN)
    row += 1

    # header
    hdr = f"  {'PID':>7}  {'USER':<12}  {'NAME':<20}  {'CPU%':>6}  {'MEM%':>6}  {'THR':>4}  STATUS"
    safe_add(win, row, 0, hdr[:cols-1],
             curses.color_pair(C_CYAN) | curses.A_BOLD | curses.A_UNDERLINE)
    row += 1

    for p in procs:
        cpu    = p["cpu_percent"] or 0.0
        mem    = p["memory_percent"] or 0.0
        cp     = color_for(cpu)
        ico    = status_icon(cpu)
        name   = (p["name"] or "?")[:20].ljust(20)
        user   = (p["username"] or "?")[:12].ljust(12)
        status = p["status"] or "?"
        thr    = p["num_threads"] or 0
        # pid in white, user in cyan, name in green/yellow/red
        safe_add(win, row, 2,
                 f" {ico}", curses.color_pair(cp) | curses.A_BOLD)
        safe_add(win, row, 5,
                 f" {p['pid']:>7} ", curses.color_pair(C_WHITE))
        safe_add(win, row, 15,
                 f" {user} ", curses.color_pair(C_CYAN))
        safe_add(win, row, 29,
                 f" {name} ", curses.color_pair(cp))
        safe_add(win, row, 51,
                 f" {cpu:>6.1f}  {mem:>6.2f}  {thr:>4}  {status}",
                 curses.color_pair(C_WHITE), cols)
        row += 1

    box_bot(win, row, cols)
    return row + 1

# ── main ──────────────────────────────────────────────────────────────────────

def main(stdscr):
    global sort_by, frame_count

    curses.curs_set(0)
    stdscr.nodelay(True)
    curses.start_color()
    curses.use_default_colors()

    curses.init_pair(C_GREEN,   curses.COLOR_GREEN,   -1)
    curses.init_pair(C_YELLOW,  curses.COLOR_YELLOW,  -1)
    curses.init_pair(C_RED,     curses.COLOR_RED,     -1)
    curses.init_pair(C_CYAN,    curses.COLOR_CYAN,    -1)
    curses.init_pair(C_FOOTER,  curses.COLOR_BLACK,   curses.COLOR_GREEN)
    curses.init_pair(C_BORDER,  curses.COLOR_GREEN,   -1)
    curses.init_pair(C_MAGENTA, curses.COLOR_MAGENTA, -1)
    curses.init_pair(C_BLUE,    curses.COLOR_BLUE,    -1)
    curses.init_pair(C_WHITE,   curses.COLOR_WHITE,   -1)

    psutil.cpu_percent(percpu=True)
    time.sleep(0.3)

    while True:
        frame_count += 1
        stdscr.erase()
        rows, cols = stdscr.getmaxyx()

        try:
            row = 0
            row = draw_arch_tag(stdscr, row, cols)
            row = draw_banner(stdscr, row, cols)
            row = draw_datetime_bar(stdscr, row, cols)
            hline(stdscr, row, cols, "═", C_BORDER)
            row += 1

            row = draw_cpu(stdscr, row, cols)
            row = draw_memory(stdscr, row, cols)
            if row < rows - 5: row = draw_load_avg(stdscr, row, cols)
            if row < rows - 5: row = draw_disk(stdscr, row, cols)
            if row < rows - 5: row = draw_network(stdscr, row, cols)
            if row < rows - 5: row = draw_sensors(stdscr, row, cols)
            if row < rows - 5: row = draw_battery(stdscr, row, cols)
            if row < rows - 5:
                max_p = max(3, rows - row - 3)
                row = draw_processes(stdscr, row, cols, max_procs=max_p)

        except curses.error:
            pass

        # footer bar
        try:
            now    = datetime.now().strftime("%H:%M:%S")
            footer = (f"  {ICO_CPU}[q]uit  [r]efresh  [c]cpu  [p]mem"
                      f"  │  refresh:{REFRESH}s  frame:{frame_count}"
                      f"  │  {now}  ")
            stdscr.attron(curses.color_pair(C_FOOTER) | curses.A_BOLD)
            stdscr.addstr(rows - 1, 0, footer.ljust(cols - 1))
            stdscr.attroff(curses.color_pair(C_FOOTER) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()

        for _ in range(REFRESH * 10):
            key = stdscr.getch()
            if key in (ord("q"), ord("Q"), 27): return
            if key in (ord("r"), ord("R")):     break
            if key in (ord("c"), ord("C")):     sort_by = "cpu"
            if key in (ord("p"), ord("P")):     sort_by = "mem"
            time.sleep(0.1)


if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        print("Install psutil first:  pip install psutil")
        raise SystemExit(1)
    curses.wrapper(main)
