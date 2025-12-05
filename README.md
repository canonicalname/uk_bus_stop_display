# uk_bus_stop_display
A basic tool to show the distance of relevant busses from a given UK bus stop. Uses the Bus Open Data Service (BODS) and displays on a SSD1322 OLED.
![alt text](https://github.com/canonicalname/uk_bus_stop_display/blob/main/display.png "Poor quality photo of the display in action")

# Things you will likely need
- A Raspberry Pi, I used an old Pi Zero W
- An SD1322 OLED screen, I got this one from Amazon https://amzn.eu/d/czxcd94
- An API key from https://data.bus-data.dft.gov.uk/, this should be added to the API_KEY in bus_stop.py
- Also in bus_stop.py, details of busses that you want to track, specifically:
-- The line reference, for example this is '1': https://bustimes.org/services/1-gillingham-university-of-medway-dockside-outlet
-- The route origin location code which you can find from the the route details, e.g. 'Gillingham The Strand' is 249000000619 from the URL https://bustimes.org/stops/249000000619
-- The route destination location code which can be found in a similar way
- The longitude and latitude of the bus-stop you want to monitor, eg https://maps.app.goo.gl/Vck7ME3WvZaBKWhV6 is 51.3967309,0.5390952. This should also go into bus_stop.py.

# Notes on the display
 The SD1322 display seems to support a couple of different protocols. To get mine to work I had to break a trace and solder another. Specifically to get 4 wire SPI mode, rather than the default 8080 parallel mode. Check the documentation on yours to see what you have but for mine it had to be:

- **R5: Bridged** ✓
- **R6: Open** (no solder)
- **R7: Open** (no solder)
- **R8: Bridged** ✓

 # Pin mappings
 I had help from Kiro on this, here's what works for me

### Raspberry Pi to SSD1322 Display

| Display Pin | Symbol | Function | → | Raspberry Pi Pin | GPIO | Notes |
|-------------|--------|----------|---|------------------|------|-------|
| 1 | VSS | Ground | → | Pin 6 (or any GND) | GND | Power ground |
| 2 | VCC_IN | Power 3.3V | → | Pin 1 or 17 | 3.3V | Power supply |
| 3 | NC | Not Connected | → | - | - | Leave unconnected |
| 4 | D0/CLK | Serial Clock | → | Pin 23 | GPIO 11 (SCLK) | SPI clock |
| 5 | D1/DIN | Serial Data | → | Pin 19 | GPIO 10 (MOSI) | SPI data out |
| 6-11 | D2-D7 | Data Lines | → | - | - | Not used in SPI mode |
| 12 | E/RD# | Enable/Read | → | - | - | Not used in SPI mode |
| 13 | R/W# | Read/Write | → | - | - | Not used in SPI mode |
| 14 | D/C# | Data/Command | → | Pin 18 | GPIO 24 | Data/Command select |
| 15 | RES# | Reset | → | Pin 22 | GPIO 25 | Reset signal |
| 16 | CS# | Chip Select | → | Pin 24 | GPIO 8 (CE0) | SPI chip select |

## Summary - Required Connections (7 wires)

**Power (2 wires):**
- Display Pin 1 (VSS) → Raspberry Pi Pin 6 (GND)
- Display Pin 2 (VCC_IN) → Raspberry Pi Pin 1 (3.3V)

**SPI Data (2 wires):**
- Display Pin 4 (D0/CLK) → Raspberry Pi Pin 23 (GPIO 11 SCLK)
- Display Pin 5 (D1/DIN) → Raspberry Pi Pin 19 (GPIO 10 MOSI)

**Control Signals (3 wires):**
- Display Pin 14 (D/C#) → Raspberry Pi Pin 18 (GPIO 24)
- Display Pin 15 (RES#) → Raspberry Pi Pin 22 (GPIO 25)
- Display Pin 16 (CS#) → Raspberry Pi Pin 24 (GPIO 8 CE0)

## Verification of the display

After wiring, verify SPI is enabled:

```bash
# Check SPI is enabled
lsmod | grep spi
```

If not you can configure with:
   ```bash
   sudo raspi-config
   # Navigate to: Interface Options → SPI → Enable
   # Reboot when prompted
   ```

# Bus Stop Display - Installation Instructions

## Prerequisites

Before setting up auto-start, ensure your Raspberry Pi is properly configured:

**Install system dependencies**:
   ```bash
   sudo apt-get update
   sudo apt-get install libopenjp2-7 python3-venv python3-pip
   ```

## Initial Setup

### 1. Create a virtual environment

```bash
cd /home/pi/bus_stop

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### 2. Install Python dependencies

```bash
# Make sure you're in the virtual environment (you should see (.venv) in your prompt)
pip install -r requirements.txt
```

This will install:
- `luma.oled` - OLED display driver
- `pillow` - Image processing
- `RPi.GPIO` - GPIO control
- `spidev` - SPI communication
- `requests` - HTTP requests for bus API

### 3. Test the display manually

```bash
# Still in the virtual environment
sudo $(which python3) ssd1322_advanced.py
```
If everything works, you should see a variety of output on the screen.

If you have your API keys, buses and bus stop configured you can try the app with:

```bash
# Still in the virtual environment
sudo $(which python3) bus_stop.py --once
```
If this works, you should see bus data fetched and displayed in the console.

## Setup for Auto-Start on Boot

Follow these steps to make the bus stop display run automatically when your Raspberry Pi boots up or controllable with cron jobs.

### 4. Make scripts executable

```bash
cd /home/pi/bus_stop
chmod +x start_bus_display.sh
chmod +x clear_display.py
```

### 5. Create and configure the log file

```bash
cd /home/pi/bus_stop
touch bus_display.log
chmod 644 bus_display.log
```

### 6. Update the service file paths (if needed)

If your bus_stop directory is not at `/home/pi/bus_stop`, edit the `bus-display.service` file and update these lines:
- `WorkingDirectory=/home/pi/bus_stop`
- `ExecStart=/home/pi/bus_stop/start_bus_display.sh`
- `StandardOutput` and `StandardError` paths

### 7. Install the systemd service

```bash
# Copy the service file to systemd directory
sudo cp bus-display.service /etc/systemd/system/

# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable bus-display.service

# If you want the service to run to a schedule, check SCHEDULE.MD

# Start the service now (without rebooting)
sudo systemctl start bus-display.service
```

### 8. Check the service status

```bash
# Check if the service is running
sudo systemctl status bus-display.service

# View the logs
tail -f /home/pi/bus_stop/bus_display.log
```

### 9. Useful commands

```bash
# Stop the service
sudo systemctl stop bus-display.service

# Restart the service
sudo systemctl restart bus-display.service

# Disable auto-start on boot
sudo systemctl disable bus-display.service

# View service logs
sudo journalctl -u bus-display.service -f
```

## Troubleshooting

### Service won't start
1. Check the log file: `cat /home/pi/bus_stop/bus_display.log`
2. Verify paths in the service file are correct
3. Ensure the script is executable: `ls -l start_bus_display.sh`
4. Check for Python errors: `python3 bus_stop.py --once`

### Display not showing
1. Verify SPI is enabled: `lsmod | grep spi`
2. Check wiring connections
3. Test manually: `sudo python3 bus_stop.py`

### Network issues
The script waits up to 60 seconds for network connectivity. If your network takes longer to connect, increase the loop count in `start_bus_display.sh`.

## Manual Testing

To test the startup script manually:

```bash
cd /home/pi/bus_stop
./start_bus_display.sh
```

Press Ctrl+C to stop.

# Bus Stop Display - Scheduling Guide

## Overview

You can schedule the bus display to run only on specific days and times using cron jobs. This is useful if you only need the display during commute hours or weekdays.

## Setup

### 1. Make the schedule script executable if it isn't already

```bash
cd /home/pi/bus_stop
chmod +x schedule_display.sh
```

### 2. Allow pi user to control the service without password

Create a sudoers file to allow the pi user to start/stop the service:

```bash
sudo visudo -f /etc/sudoers.d/bus-display
```

Add this line:
```
pi ALL=(ALL) NOPASSWD: /bin/systemctl start bus-display.service, /bin/systemctl stop bus-display.service
```

Save and exit (Ctrl+X, then Y, then Enter).

### 3. Disable auto-start on boot

Since we're using cron to control when it runs:

```bash
sudo systemctl disable bus-display.service
```

### 4. Set up cron jobs

Edit the crontab:

```bash
crontab -e
```

## Example Schedules

### Example 1: Weekdays only, 6 AM to 9 PM

```cron
# Start display at 6:00 AM Monday-Friday
0 6 * * 1-5 /home/pi/bus_stop/schedule_display.sh start

# Stop display at 9:00 PM Monday-Friday
0 21 * * 1-5 /home/pi/bus_stop/schedule_display.sh stop
```

### Example 2: Morning and evening commute times

```cron
# Morning commute: Start at 6:30 AM, stop at 9:30 AM (Mon-Fri)
30 6 * * 1-5 /home/pi/bus_stop/schedule_display.sh start
30 9 * * 1-5 /home/pi/bus_stop/schedule_display.sh stop

# Evening commute: Start at 4:00 PM, stop at 7:00 PM (Mon-Fri)
0 16 * * 1-5 /home/pi/bus_stop/schedule_display.sh start
0 19 * * 1-5 /home/pi/bus_stop/schedule_display.sh stop
```

### Example 3: School days only (Mon-Fri, 7 AM to 4 PM)

```cron
# Start at 7:00 AM Monday-Friday
0 7 * * 1-5 /home/pi/bus_stop/schedule_display.sh start

# Stop at 4:00 PM Monday-Friday
0 16 * * 1-5 /home/pi/bus_stop/schedule_display.sh stop
```

### Example 4: Weekends only

```cron
# Start at 8:00 AM Saturday-Sunday
0 8 * * 6-7 /home/pi/bus_stop/schedule_display.sh start

# Stop at 10:00 PM Saturday-Sunday
0 22 * * 6-7 /home/pi/bus_stop/schedule_display.sh stop
```

### Example 5: Different times for different days

```cron
# Monday-Friday: 6 AM to 9 PM
0 6 * * 1-5 /home/pi/bus_stop/schedule_display.sh start
0 21 * * 1-5 /home/pi/bus_stop/schedule_display.sh stop

# Saturday: 8 AM to 6 PM
0 8 * * 6 /home/pi/bus_stop/schedule_display.sh start
0 18 * * 6 /home/pi/bus_stop/schedule_display.sh stop

# Sunday: Off (no cron entries)
```

## Cron Time Format

```
* * * * * command
│ │ │ │ │
│ │ │ │ └─── Day of week (0-7, 0 and 7 are Sunday)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

### Day of week values:
- 0 or 7 = Sunday
- 1 = Monday
- 2 = Tuesday
- 3 = Wednesday
- 4 = Thursday
- 5 = Friday
- 6 = Saturday

### Ranges and lists:
- `1-5` = Monday through Friday
- `6,7` or `6-7` = Saturday and Sunday
- `*` = Every (e.g., every day, every hour)

## Verify Cron Jobs

To see your current cron jobs:

```bash
crontab -l
```

## Testing

Test the schedule script manually:

```bash
# Start the service
./schedule_display.sh start

# Check if it's running
sudo systemctl status bus-display.service

# Stop the service
./schedule_display.sh stop
```

## Troubleshooting

### Cron jobs not running

1. Check cron is running:
   ```bash
   sudo systemctl status cron
   ```

2. Check cron logs:
   ```bash
   grep CRON /var/log/syslog
   ```

3. Verify the script path is absolute (starts with `/home/pi/...`)

### Permission issues

Make sure you added the sudoers entry correctly:
```bash
sudo cat /etc/sudoers.d/bus-display
```

### Service won't start/stop

Test manually:
```bash
sudo systemctl start bus-display.service
sudo systemctl status bus-display.service
```

## Alternative: Systemd Timers

If you prefer systemd timers over cron, you can create `.timer` files. Let me know if you'd like instructions for that approach.

## Logging

Cron output is logged to syslog. To see cron-related messages:

```bash
grep CRON /var/log/syslog | tail -20
```

The bus display itself logs to `/home/pi/bus_stop/bus_display.log`.
