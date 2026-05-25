sysmon 👾

A hacker-aesthetic live system dashboard for Arch Linux, built with pure Python.

   >>  ARCH USES ME BTW  <<
   
    ███████╗██╗   ██╗███████╗███╗   ███╗ ██████╗ ███╗   ██╗
    ██╔════╝╚██╗ ██╔╝██╔════╝████╗ ████║██╔═══██╗████╗  ██║
    ███████╗ ╚████╔╝ ███████╗██╔████╔██║██║   ██║██╔██╗ ██║
    ╚════██║  ╚██╔╝  ╚════██║██║╚██╔╝██║██║   ██║██║╚██╗██║
    ███████║   ██║   ███████║██║ ╚═╝ ██║╚██████╔╝██║ ╚████║
    ╚══════╝   ╚═╝   ╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
   No frameworks. No TUI libraries. Just psutil + curses, the way it should be.

## Features:
What it shows
⚙ CPUOverall + per-core usage bars, sparkline history, frequency, core/thread count
▤ MemoryRAM & Swap bars with sparkline, available/cached/buffers breakdown
⌛ Load Average1min / 5min / 15min load as bars relative to core count
🖴 DiskAll mounted partitions, fstype, usage bars, total I/O read/write counters
⇅ NetworkPer-interface live ↑↓ bandwidth (bytes/sec), IP, totals, errors, drops
🌡 TemperaturesCPU/chip sensor readings with high/critical thresholds
⚡ BatteryCharge %, charging status, estimated time remaining◈ ProcessesTop N processes sortable by CPU or MEM, with PID, user, threads, status


## Requirements:
Python 3.6+
psutil

## Configuration:
At the top of the file you can tweak:
pythonREFRESH       = 2     # seconds between updates
SPARKLINE_LEN = 30    # how many data points in the sparkline history
GLITCH_PROB   = 0.04  # probability of a glitch char in the banner per frame

## How to use:
fork the repo and get the code
sudo cp sysmon.py /usr/local/bin/sysmon
sudo chmod +x /usr/local/bin/sysmon # run by just by sysmon in your terminal 

## Built with:
psutil — system stats
curses — terminal UI (stdlib)
collections.deque — sparkline history ring buffer
platform, socket, os, datetime, random — all stdlib

## preview of my ghostty terminal
<img width="955" height="1045" alt="ghmon" src="https://github.com/user-attachments/assets/a21a3e57-ffbb-4688-a858-eeda2564ed55" />



## preview of my kitty terminal
<img width="1920" height="1080" alt="Screenshot_20260525_154131-1" src="https://github.com/user-attachments/assets/a2b7c709-d197-4b3d-83d4-a2c967a53412" />



##preview
Author
##preview
Ujjwal Mishra 
— CSE-AI @ GGSIPU-USICT
2026
