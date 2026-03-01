"""
Curved Route Analysis Tool

Compares straight vs. curved paths for population avoidance.
Shows whether it's worth adding extra distance to reduce casualty exposure.
"""

from kimDroneGoon.geo import geodata
from kimDroneGoon.visualize import visualizer
from curved_route_optimizer import CurvedRouteOptimizer, analyze_population_avoidance_value


def main():
    print("="*70)
    print("CURVED ROUTE ANALYSIS")
    print("="*70)
    
    # Initialize data
    print("\n[*] Loading geospatial data...")
    data = geodata(
        "kimDroneGoon/datasets/worldpopHK/hkg_ppp_2020_UNadj_constrained.tif",
        "kimDroneGoon/datasets/LUMHK_RasterGrid_2024/BLU.tif",
        "kimDroneGoon/datasets/sandboxZones/map.geojson"
    )
    
    # Get optimized drone path
    print("[*] Computing optimized drone path...")
    v = visualizer(data)
    route_gdf = v.getOptimizedDronePath()
    
    if route_gdf is None or len(route_gdf) < 2:
        print("[!] Could not compute drone path")
        return
    
    print(f"[*] Route has {len(route_gdf)} waypoints")
    
    # Analyze population avoidance value
    print("\n[*] Analyzing population avoidance value...")
    results = analyze_population_avoidance_value(data, route_gdf)
    
    print("\n✓ Analysis complete!")


if __name__ == '__main__':
    main()
