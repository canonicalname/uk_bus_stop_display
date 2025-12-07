#!/usr/bin/env python3
"""
Bus Stop Display - Real-time bus tracking for OLED display
Fetches bus data from UK Bus Open Data API and displays on SSD1322 OLED
"""

import requests
import xml.etree.ElementTree as ET
from math import radians, sin, cos, sqrt, atan2
from typing import Optional, List, Dict
from dataclasses import dataclass
import time
import random
from datetime import datetime, timedelta, timezone
from luma.core.interface.serial import spi
from luma.oled.device import ssd1322
from luma.core.render import canvas
from PIL import ImageFont


# API Configuration
API_BASE_URL = "https://data.bus-data.dft.gov.uk/api/v1/datafeed/"
API_KEY = "" # PUT YOUR API KEY HERE

# Bus Stop Location
BUS_STOP_LATITUDE = # PUT YOUR STOP LATITUDE HERE
BUS_STOP_LONGITUDE = # PUT YOUR STOP LONGITUDE HERE (Be sure to get these the right way around)

# Cardinal filter, ignore busses which are to this direction of the bus stop
# This filters out busses that have gone past your stop, eg. if West of my stop then I'm not interested
# You can use, N, S, E or W here
CARDINAL_FILTER = "W"

# Bus routes to monitor - list of (operator_ref, line_ref, origin_ref, destination_ref)
# You can add as many routes as you like, https://bustimes.org/ is very helpful here
BUS_ROUTES = [
    ("AKSS", "1", "249000000619", "249000000700") # e.g Arriva Kent and Surrey, Route 1, Gillingham The Strand (NW-bound) to Chatham Railway Station (Stop B)
]

@dataclass
class Location:
    """Represents a geographic location with latitude and longitude"""
    latitude: float
    longitude: float


@dataclass
class Bus:
    """Represents a bus with its current location and details"""
    line_ref: str
    operator_ref: str
    origin_ref: str
    destination_ref: str
    vehicle_ref: str
    origin_name: str = ""
    destination_name: str = ""
    recorded_at: str = ""
    location: Optional[Location] = None
    
    def distance_to(self, target: Location) -> float:
        """
        Calculate distance to a target location in meters
        Uses Haversine formula for great-circle distance
        """
        if self.location is None:
            return float('inf')
        
        return calculate_distance(self.location, target)


@dataclass
class BusStop:
    """Represents a bus stop with its location"""
    name: str
    stop_ref: str
    location: Location
    
    def distance_from_bus(self, bus: Bus) -> float:
        """Calculate distance from this stop to a bus in meters"""
        return bus.distance_to(self.location)


def calculate_distance(loc1: Location, loc2: Location) -> float:
    """
    Calculate distance between two locations in meters using Haversine formula
    
    Args:
        loc1: First location (latitude, longitude)
        loc2: Second location (latitude, longitude)
    
    Returns:
        Distance in meters
    """
    # Earth's radius in meters
    R = 6371000
    
    # Convert to radians
    lat1, lon1 = radians(loc1.latitude), radians(loc1.longitude)
    lat2, lon2 = radians(loc2.latitude), radians(loc2.longitude)
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    distance = R * c
    return distance


def calculate_bearing(from_loc: Location, to_loc: Location) -> float:
    """
    Calculate bearing from one location to another in degrees (0-360)
    0° = North, 90° = East, 180° = South, 270° = West
    
    Args:
        from_loc: Starting location
        to_loc: Destination location
    
    Returns:
        Bearing in degrees (0-360)
    """
    lat1, lon1 = radians(from_loc.latitude), radians(from_loc.longitude)
    lat2, lon2 = radians(to_loc.latitude), radians(to_loc.longitude)
    
    dlon = lon2 - lon1
    
    x = sin(dlon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    
    bearing = atan2(x, y)
    bearing = (bearing * 180 / 3.14159265359 + 360) % 360
    
    return bearing


def get_cardinal_direction(bearing: float) -> str:
    """
    Convert bearing to cardinal direction
    
    Args:
        bearing: Bearing in degrees (0-360)
    
    Returns:
        Cardinal direction (N, NE, E, SE, S, SW, W, NW)
    """
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    index = round(bearing / 45) % 8
    return directions[index]


def is_in_filtered_direction(bus_location: Location, stop_location: Location, filter_direction: str) -> bool:
    """
    Check if a bus is in the filtered direction relative to the stop
    Uses broader ranges: N filters 315-45°, E filters 45-135°, S filters 135-225°, W filters 225-315°
    
    Args:
        bus_location: Location of the bus
        stop_location: Location of the bus stop
        filter_direction: Cardinal direction to filter (N, E, S, W)
    
    Returns:
        True if bus is in the filtered direction (should be excluded), False otherwise
    """
    if not filter_direction:
        return False
    
    # Calculate bearing from stop to bus
    bearing = calculate_bearing(stop_location, bus_location)
    
    filter_dir = filter_direction.upper()
    
    # Define broader ranges for each cardinal direction
    # N: 270° to 90° (includes NW, N, NE)
    # E: 0° to 180° (includes NE, E, SE)
    # S: 90° to 270° (includes SE, S, SW)
    # W: 180° to 359° (includes SW, W, NW)
    
    if filter_dir == "N":
        return bearing >= 270 or bearing < 90
    elif filter_dir == "E":
        return 0 <= bearing < 180
    elif filter_dir == "S":
        return 90 <= bearing < 270
    elif filter_dir == "W":
        return 180 <= bearing <=359
    else:
        # If it's a diagonal direction (NE, SE, SW, NW), use narrower range
        direction = get_cardinal_direction(bearing)
        return direction == filter_dir


def is_bus_data_fresh(recorded_at: str, max_age_minutes: int = 15) -> bool:
    """
    Check if bus data is fresh (not older than max_age_minutes)
    
    Args:
        recorded_at: ISO 8601 timestamp string (e.g., "2025-12-05T09:46:52+00:00")
        max_age_minutes: Maximum age in minutes (default 15)
    
    Returns:
        True if data is fresh, False if stale or invalid
    """
    if not recorded_at:
        return False
    
    try:
        # Parse the ISO 8601 timestamp
        recorded_time = datetime.fromisoformat(recorded_at.replace('Z', '+00:00'))
        
        # Get current time in UTC
        current_time = datetime.now(timezone.utc)
        
        # Calculate age
        age = current_time - recorded_time
        
        # Check if within acceptable age
        return age <= timedelta(minutes=max_age_minutes)
    except (ValueError, AttributeError) as e:
        print(f"Error parsing timestamp '{recorded_at}': {e}")
        return False


def filter_buses_by_freshness(buses: List[Bus], max_age_minutes: int = 15) -> List[Bus]:
    """
    Filter out buses with stale data (older than max_age_minutes)
    
    Args:
        buses: List of Bus objects
        max_age_minutes: Maximum age in minutes (default 15)
    
    Returns:
        Filtered list of Bus objects with fresh data
    """
    filtered = []
    for bus in buses:
        if is_bus_data_fresh(bus.recorded_at, max_age_minutes):
            filtered.append(bus)
    
    return filtered


def filter_buses_by_direction(buses: List[Bus], stop: BusStop, filter_direction: str) -> List[Bus]:
    """
    Filter out buses that are in the specified direction from the stop
    (i.e., buses that have already passed the stop)
    
    Args:
        buses: List of Bus objects
        stop: BusStop object
        filter_direction: Cardinal direction to filter out (e.g., "WEST")
    
    Returns:
        Filtered list of Bus objects
    """
    if not filter_direction:
        return buses
    
    filtered = []
    for bus in buses:
        if bus.location:
            if not is_in_filtered_direction(bus.location, stop.location, filter_direction):
                filtered.append(bus)
    
    return filtered


def fetch_bus_data(
    operator_ref: str,
    line_ref: str,
    origin_ref: str,
    destination_ref: str,
    api_key: str = API_KEY,
    base_url: str = API_BASE_URL
) -> Optional[str]:
    """
    Fetch bus data from the UK Bus Open Data API
    
    Args:
        operator_ref: Operator reference code (e.g., "AKSS")
        line_ref: Line/route reference (e.g., "7")
        origin_ref: Origin stop reference
        destination_ref: Destination stop reference
        api_key: API key for authentication
        base_url: Base URL for the API
    
    Returns:
        XML response as string, or None if request fails
    """
    params = {
        "api_key": api_key,
        "operatorRef": operator_ref,
        "lineRef": line_ref,
        "originRef": origin_ref,
        "destinationRef": destination_ref
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching bus data: {e}")
        return None


def parse_buses_from_xml(xml_data: str) -> List[Bus]:
    """
    Parse bus data from SIRI XML response and create Bus objects
    
    Args:
        xml_data: XML response string from the API
    
    Returns:
        List of Bus objects with location data
    """
    buses = []
    
    try:
        # Parse XML
        root = ET.fromstring(xml_data)
        
        # Define namespace for SIRI XML
        ns = {'siri': 'http://www.siri.org.uk/siri'}
        
        # Find all VehicleActivity elements
        vehicle_activities = root.findall('.//siri:VehicleActivity', ns)
        
        for activity in vehicle_activities:
            # Extract MonitoredVehicleJourney data
            journey = activity.find('.//siri:MonitoredVehicleJourney', ns)
            if journey is None:
                continue
            
            # Extract location
            location = None
            vehicle_location = journey.find('.//siri:VehicleLocation', ns)
            if vehicle_location is not None:
                lon_elem = vehicle_location.find('siri:Longitude', ns)
                lat_elem = vehicle_location.find('siri:Latitude', ns)
                
                if lon_elem is not None and lat_elem is not None:
                    try:
                        longitude = float(lon_elem.text)
                        latitude = float(lat_elem.text)
                        location = Location(latitude=latitude, longitude=longitude)
                    except (ValueError, TypeError):
                        pass
            
            # Extract other details
            line_ref = journey.find('siri:LineRef', ns)
            operator_ref = journey.find('siri:OperatorRef', ns)
            origin_ref = journey.find('siri:OriginRef', ns)
            destination_ref = journey.find('siri:DestinationRef', ns)
            vehicle_ref = journey.find('siri:VehicleRef', ns)
            origin_name = journey.find('siri:OriginName', ns)
            destination_name = journey.find('siri:DestinationName', ns)
            recorded_at = activity.find('siri:RecordedAtTime', ns)
            
            bus = Bus(
                line_ref=line_ref.text if line_ref is not None else 'Unknown',
                operator_ref=operator_ref.text if operator_ref is not None else 'Unknown',
                origin_ref=origin_ref.text if origin_ref is not None else 'Unknown',
                destination_ref=destination_ref.text if destination_ref is not None else 'Unknown',
                vehicle_ref=vehicle_ref.text if vehicle_ref is not None else 'Unknown',
                origin_name=origin_name.text if origin_name is not None else '',
                destination_name=destination_name.text if destination_name is not None else '',
                recorded_at=recorded_at.text if recorded_at is not None else '',
                location=location
            )
            buses.append(bus)
            
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
    except Exception as e:
        print(f"Error processing bus data: {e}")
    
    return buses


def display_bus_distances(buses: List[Bus], stop: BusStop, show_filtered: bool = False):
    """
    Display the location and distance of each bus from the stop
    
    Args:
        buses: List of Bus objects
        stop: BusStop object to calculate distances from
        show_filtered: Whether to show filtered out buses
    """
    print(f"\n{'='*70}")
    print(f"Bus Stop: {stop.name}")
    print(f"Location: {stop.location.latitude:.6f}, {stop.location.longitude:.6f}")
    if CARDINAL_FILTER:
        print(f"Filtering out buses to the {CARDINAL_FILTER} (already passed)")
    print(f"{'='*70}")
    
    if not buses:
        print("No buses found")
        return
    
    print(f"\nFound {len(buses)} bus(es):\n")
    
    # Sort buses by distance from stop
    buses_with_distance = []
    for bus in buses:
        if bus.location:
            distance = stop.distance_from_bus(bus)
            bearing = calculate_bearing(stop.location, bus.location)
            direction = get_cardinal_direction(bearing)
            buses_with_distance.append((bus, distance, direction))
    
    buses_with_distance.sort(key=lambda x: x[1])
    
    for i, (bus, distance, direction) in enumerate(buses_with_distance, 1):
        print(f"Bus #{i} - Line {bus.line_ref} (Vehicle {bus.vehicle_ref})")
        print(f"  Route: {bus.origin_name} → {bus.destination_name}")
        print(f"  Location: {bus.location.latitude:.6f}, {bus.location.longitude:.6f}")
        print(f"  Direction from stop: {direction}")
        print(f"  Distance from stop: {distance:.2f} meters ({distance/1000:.2f} km)")
        print(f"  Last updated: {bus.recorded_at}")
        print()


def test_with_sample_file():
    """Test parsing with the sample XML file"""
    print("Testing with sample_output.xml...")
    
    try:
        with open('sample_output.xml', 'r') as f:
            xml_data = f.read()
        
        stop = BusStop(
            name="My Bus Stop",
            stop_ref="2400A013900A",
            location=Location(latitude=BUS_STOP_LATITUDE, longitude=BUS_STOP_LONGITUDE)
        )
        
        buses = parse_buses_from_xml(xml_data)
        
        # Apply freshness filter
        fresh_buses = filter_buses_by_freshness(buses, max_age_minutes=15)
        
        # Apply cardinal direction filter
        filtered_buses = filter_buses_by_direction(fresh_buses, stop, CARDINAL_FILTER)
        
        print(f"\nTotal buses: {len(buses)}")
        print(f"Fresh buses (< 15 min old): {len(fresh_buses)}")
        print(f"After direction filtering: {len(filtered_buses)}")
        
        display_bus_distances(filtered_buses, stop)
        
    except FileNotFoundError:
        print("sample_output.xml not found")


def fetch_all_buses(routes: List[tuple], verbose: bool = True) -> List[Bus]:
    """
    Fetch bus data for multiple routes and combine into a single list
    
    Args:
        routes: List of tuples (operator_ref, line_ref, origin_ref, destination_ref)
        verbose: Whether to print progress messages
    
    Returns:
        Combined list of Bus objects from all routes
    """
    all_buses = []
    
    for operator_ref, line_ref, origin_ref, destination_ref in routes:
        if verbose:
            print(f"Fetching Line {line_ref} ({operator_ref})...")
        
        xml_data = fetch_bus_data(
            operator_ref=operator_ref,
            line_ref=line_ref,
            origin_ref=origin_ref,
            destination_ref=destination_ref
        )
        
        if xml_data:
            buses = parse_buses_from_xml(xml_data)
            all_buses.extend(buses)
            if verbose:
                print(f"  Found {len(buses)} bus(es)")
        else:
            if verbose:
                print(f"  Failed to fetch data")
    
    return all_buses


def draw_bus_icon(draw, x, y, height=15):
    """
    Draw a simple bus icon using basic shapes
    
    Args:
        draw: PIL ImageDraw object
        x, y: Top-left position
        height: Height of the bus icon (default 15px)
    """
    # Calculate proportional width (bus is roughly 1.5x height)
    width = int(height * 1.5)
    
    # Main bus body (rectangle)
    body_height = int(height * 0.7)
    draw.rectangle((x, y, x + width, y + body_height), outline="white", fill="black")
    
    # Windows (3 small rectangles)
    window_width = int(width * 0.22)
    window_height = int(body_height * 0.3)
    window_y = y + 2
    window_spacing = 1
    
    # Left window
    draw.rectangle(
        (x + 2, window_y, x + 2 + window_width, window_y + window_height),
        outline="white",
        fill="white"
    )
    
    # Middle window
    middle_x = x + 2 + window_width + window_spacing
    draw.rectangle(
        (middle_x, window_y, middle_x + window_width, window_y + window_height),
        outline="white",
        fill="white"
    )
    
    # Right window
    draw.rectangle(
        (x + width - window_width - 2, window_y, x + width - 2, window_y + window_height),
        outline="white",
        fill="white"
    )
    
    # Wheels (2 circles, 50% larger)
    wheel_radius = int(height * 0.15 * 1.5)  # 50% larger
    wheel_y = y + body_height - wheel_radius
    
    # Left wheel
    draw.ellipse(
        (x + 3, wheel_y, x + 3 + wheel_radius * 2, wheel_y + wheel_radius * 2),
        outline="white",
        fill="black"
    )
    
    # Right wheel
    draw.ellipse(
        (x + width - wheel_radius * 2 - 3, wheel_y, x + width - 3, wheel_y + wheel_radius * 2),
        outline="white",
        fill="black"
    )
    
    # Front bumper (small rectangle)
    bumper_width = 1
    draw.rectangle(
        (x + width, y + int(body_height * 0.3), x + width + bumper_width, y + int(body_height * 0.9)),
        fill="white"
    )


def draw_progress_bar(draw, x, y, width, height, progress, max_value=20.0):
    """
    Draw a progress bar showing distance (0-20km range)
    
    Args:
        draw: PIL ImageDraw object
        x, y: Top-left position
        width, height: Dimensions of the bar
        progress: Current value (distance in km)
        max_value: Maximum value (default 20km)
    """
    # Clamp progress to 0-max_value range
    progress = max(0, min(progress, max_value))
    
    # Calculate fill width (inverted - closer = more filled)
    fill_ratio = 1.0 - (progress / max_value)
    fill_width = int(width * fill_ratio)
    
    # Draw outer border
    draw.rectangle((x, y, x + width, y + height), outline="white", fill="black")
    
    # Draw filled portion
    if fill_width > 0:
        draw.rectangle((x + 1, y + 1, x + fill_width - 1, y + height - 1), fill="white")


def display_buses_on_oled(device, buses: List[Bus], stop: BusStop):
    """
    Display top 3 buses on OLED with progress bars and clock
    
    Args:
        device: OLED device object
        buses: List of Bus objects sorted by distance
        stop: BusStop object
    """
    with canvas(device) as draw:
        # Get top 3 buses
        top_buses = buses[:3]
        
        # Display each bus on a row (rows are smaller to fit clock at bottom)
        for i, bus in enumerate(top_buses):
            if bus.location:
                distance_m = stop.distance_from_bus(bus)
                distance_km = distance_m / 1000.0
                
                # Row position (15 pixels per row for 3 rows, leaving space for clock)
                y = i * 15
                
                # Format: "1 [bus icon] 7    3.5km [progress bar]"
                order_num = str(i + 1)
                line_ref = bus.line_ref
                distance_text = f"{distance_km:.1f}km away"
                
                # Draw order number
                draw.text((2, y + 2), order_num, fill="white")
                
                # Draw bus icon
                draw_bus_icon(draw, 15, y + 1, height=12)
                
                # Draw line reference (shifted right 20px more to make room for bus icon)
                draw.text((55, y + 2), "#" + line_ref, fill="white")
                
                # Draw distance (shifted right 20px more)
                draw.text((90, y + 2), distance_text, fill="white")
                
                # Determine what to show on the right side
                if distance_m < 100:  # Less than 100 meters
                    # Show "Arriving" text
                    draw.text((device.width - 60, y + 2), "Arriving!", fill="white")
                elif distance_km < 1.0:  # Less than 1km
                    # Show "Leave now!" text
                    draw.text((device.width - 70, y + 2), "Leave now!", fill="white")
                else:
                    # Draw progress bar (right side of screen)
                    bar_x = device.width - 85
                    bar_y = y + 2
                    bar_width = 80
                    bar_height = 10
                    draw_progress_bar(draw, bar_x, bar_y, bar_width, bar_height, distance_km, max_value=20.0)
        
        # Always show time on bottom row
        current_time = datetime.now().strftime("%H:%M:%S")
        
        # Calculate center position for time
        # Approximate character width for default font
        time_width = len(current_time) * 6
        time_x = (device.width - time_width) // 2
        time_y = 50  # Bottom of screen
        
        draw.text((time_x, time_y), current_time, fill="white")


def run_display_loop():
    """
    Main loop to continuously fetch and display bus data on OLED
    Updates every 10 seconds with ±2 second jitter
    """
    # Initialize OLED display
    print("Initializing OLED display...")
    serial = spi(device=0, port=0)
    device = ssd1322(serial, width=256, height=64)

    # Set contrast (0-255, default is ~127)
    device.contrast(32)  # Adjust this value to your preference, lower settings may reduce burn-in?
    
    # Create bus stop
    stop = BusStop(
        name="My Bus Stop",
        stop_ref="2400A013900A",
        location=Location(latitude=BUS_STOP_LATITUDE, longitude=BUS_STOP_LONGITUDE)
    )
    
    print("Starting bus tracking loop...")
    print("Press Ctrl+C to exit")
    
    try:
        while True:
            # Fetch bus data
            buses = fetch_all_buses(BUS_ROUTES, verbose=False)
            
            # Apply freshness filter (remove buses with stale data)
            fresh_buses = filter_buses_by_freshness(buses, max_age_minutes=15)
            
            # Apply direction filter
            filtered_buses = filter_buses_by_direction(fresh_buses, stop, CARDINAL_FILTER)
            
            # Sort by distance
            buses_with_distance = []
            for bus in filtered_buses:
                if bus.location:
                    distance = stop.distance_from_bus(bus)
                    buses_with_distance.append((bus, distance))
            
            buses_with_distance.sort(key=lambda x: x[1])
            sorted_buses = [bus for bus, _ in buses_with_distance]
            
            # Display on OLED
            display_buses_on_oled(device, sorted_buses, stop)
            
            # Print summary to console
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Buses: {len(buses)} total, {len(fresh_buses)} fresh, {len(filtered_buses)} after direction filter, showing top {min(len(sorted_buses), 3)}")
            
            # List vehicle_ref for each tracked bus
            if sorted_buses:
                print("  Tracked buses:")
                for i, bus in enumerate(sorted_buses[:3], 1):
                    distance_km = stop.distance_from_bus(bus) / 1000.0
                    print(f"    {i}. Line {bus.line_ref} - Vehicle {bus.vehicle_ref} - {distance_km:.1f}km away")
            
            # Wait with jitter (10 ± 2 seconds)
            jitter = random.uniform(-2, 2)
            sleep_time = 10 + jitter
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        print("\nStopping display...")
        device.clear()
        print("Display cleared. Goodbye!")


def main():
    """Main function to fetch and display bus data"""
    
    # Create the bus stop with actual location
    stop = BusStop(
        name="My Bus Stop",
        stop_ref="2400A013900A",
        location=Location(latitude=BUS_STOP_LATITUDE, longitude=BUS_STOP_LONGITUDE)
    )
    
    # Fetch bus data for all configured routes
    print("Fetching bus data from API...")
    buses = fetch_all_buses(BUS_ROUTES)
    
    if not buses:
        print("No buses found")
        return
    
    # Apply freshness filter
    fresh_buses = filter_buses_by_freshness(buses, max_age_minutes=15)
    
    # Apply cardinal direction filter
    filtered_buses = filter_buses_by_direction(fresh_buses, stop, CARDINAL_FILTER)
    
    print(f"\nTotal buses: {len(buses)}")
    print(f"Fresh buses (< 15 min old): {len(fresh_buses)}")
    print(f"After direction filtering: {len(filtered_buses)}")
    
    # Display bus locations and distances
    display_bus_distances(filtered_buses, stop)


if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            test_with_sample_file()
        elif sys.argv[1] == "--once":
            # Run once without display (for testing)
            main()
        else:
            print("Usage:")
            print("  python3 bus_stop.py          - Run continuous OLED display")
            print("  python3 bus_stop.py --test   - Test with sample XML file")
            print("  python3 bus_stop.py --once   - Fetch and display once (console only)")
    else:
        # Default: run continuous display loop
        run_display_loop()
