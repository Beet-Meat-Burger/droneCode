"""
Optimized Waypoint Generation with Leg Breaking

Full pipeline: TSP routing → Break long legs → Output mission

Shows how to generate drone mission waypoints that respect:
- Population-aware routing (TSP)
- Battery constraints (max 10 km legs)
- Lowest-population waypoint insertion
"""

import csv
from kimDroneGoon.geo import geodata
from kimDroneGoon.visualize import visualizer


def generate_optimized_mission(output_file='drone_mission_waypoints.csv'):
    """
    Generates optimized waypoints with automatic leg breaking.
    """
    
    print("="*70)
    print("OPTIMIZED MISSION WAYPOINT GENERATION")
    print("="*70)
    
    # Initialize
    print("\n[*] Loading geospatial data...")
    data = geodata(
        "kimDroneGoon/datasets/worldpopHK/hkg_ppp_2020_UNadj_constrained.tif",
        "kimDroneGoon/datasets/LUMHK_RasterGrid_2024/BLU.tif",
        "kimDroneGoon/datasets/sandboxZones/map.geojson"
    )
    
    v = visualizer(data)
    
    # Step 1: Get TSP route
    print("\n[*] Step 1: Computing TSP-optimized route...")
    route_gdf = v.getOptimizedDronePath()
    
    if route_gdf is None or len(route_gdf) < 2:
        print("[!] Failed to compute route")
        return
    
    print(f"    ✓ Found {len(route_gdf)} strategic waypoints")
    
    # Step 2: Break long legs
    print("\n[*] Step 2: Breaking long legs (max 10 km)...")
    optimized_waypoints, long_legs = v.break_long_legs(route_gdf, max_leg_km=10.0)
    
    print(f"    ✓ Optimized to {len(optimized_waypoints)} waypoints")
    
    # Step 3: Export to CSV
    print(f"\n[*] Step 3: Exporting to {output_file}...")
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['waypoint_id', 'latitude', 'longitude', 'altitude_ft', 'type'])
        writer.writeheader()
        
        for idx, (lat, lng) in enumerate(optimized_waypoints):
            # Get population for reference
            try:
                pop = data.getPopulationDensity(lat, lng)
            except:
                pop = 0
            
            # Mark inserted waypoints
            waypoint_type = 'ORIGINAL' if idx < len(route_gdf) else 'INSERTED'
            
            writer.writerow({
                'waypoint_id': idx,
                'latitude': f"{lat:.6f}",
                'longitude': f"{lng:.6f}",
                'altitude_ft': 250,  # Default altitude
                'type': waypoint_type
            })
    
    print(f"    ✓ Exported {len(optimized_waypoints)} waypoints")
    
    # Step 4: Print summary
    print("\n" + "="*70)
    print("MISSION SUMMARY")
    print("="*70)
    
    print(f"\nWaypoint Breakdown:")
    print(f"  Original TSP waypoints: {len(route_gdf)}")
    print(f"  Inserted intermediate waypoints: {len(optimized_waypoints) - len(route_gdf)}")
    print(f"  Total waypoints: {len(optimized_waypoints)}")
    
    if long_legs:
        print(f"\nLong Legs Broken:")
        for leg in long_legs:
            print(f"  Leg {leg['leg'][0]}→{leg['leg'][1]}: {leg['distance_km']:.2f} km → {leg['intermediate']} insertions")
    else:
        print(f"\nLong Legs Broken: None (all legs < 10 km)")
    
    print(f"\nExport:")
    print(f"  File: {output_file}")
    print(f"  Format: CSV with waypoint coordinates")
    print(f"  Ready for: Drone mission planner upload")
    
    print("\n" + "="*70)
    print("✓ Mission generation complete!")
    print("="*70 + "\n")
    
    # Return for programmatic use
    return optimized_waypoints, long_legs


def generate_multi_altitude_missions():
    """
    Generates missions with different altitude profiles.
    Shows how waypoint needs change with altitude settings.
    """
    
    print("="*70)
    print("MULTI-ALTITUDE MISSION GENERATION")
    print("="*70)
    
    # Initialize
    print("\n[*] Loading geospatial data...")
    data = geodata(
        "kimDroneGoon/datasets/worldpopHK/hkg_ppp_2020_UNadj_constrained.tif",
        "kimDroneGoon/datasets/LUMHK_RasterGrid_2024/BLU.tif",
        "kimDroneGoon/datasets/sandboxZones/map.geojson"
    )
    
    v = visualizer(data)
    route_gdf = v.getOptimizedDronePath()
    
    if route_gdf is None:
        print("[!] Failed to compute route")
        return
    
    altitudes = [100, 250, 500]
    
    for altitude_ft in altitudes:
        print(f"\n[*] Generating mission for {altitude_ft} ft altitude...")
        
        optimized_waypoints, long_legs = v.break_long_legs(route_gdf, max_leg_km=10.0)
        
        filename = f'drone_mission_{altitude_ft}ft.csv'
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['waypoint_id', 'latitude', 'longitude', 'altitude_ft', 'type'])
            writer.writeheader()
            
            for idx, (lat, lng) in enumerate(optimized_waypoints):
                waypoint_type = 'ORIGINAL' if idx < len(route_gdf) else 'INSERTED'
                
                writer.writerow({
                    'waypoint_id': idx,
                    'latitude': f"{lat:.6f}",
                    'longitude': f"{lng:.6f}",
                    'altitude_ft': altitude_ft,
                    'type': waypoint_type
                })
        
        print(f"    ✓ {filename} ({len(optimized_waypoints)} waypoints)")
    
    print("\n" + "="*70)
    print("✓ Multi-altitude missions generated!")
    print("="*70 + "\n")


if __name__ == '__main__':
    # Generate single mission with auto leg-breaking
    waypoints, legs = generate_optimized_mission()
    
    # Or generate multiple altitude versions:
    # generate_multi_altitude_missions()
