#!/usr/bin/env python3
"""
Analyze Population Under Different Drone Paths

Calculates TOTAL population and average population per 100m square for:
1. STRAIGHT - Direct line paths between waypoints
2. ORIGINAL - Original unoptimized waypoint sequence
3. OPTIMIZED - TSP-optimized route

Each path's population is calculated by:
- Finding ALL 100m raster cells that the path line intersects
- Summing the population from all those cells
- Computing average population per cell

Usage:
    python analyze_path_population.py
"""

import math
import csv
import json
from pathlib import Path
import pandas as pd
import numpy as np
from shapely.geometry import Point, LineString
import rasterio
import rasterio.features
from rasterio.features import geometry_mask

from kimDroneGoon.geo import geodata
from kimDroneGoon.visualize import visualizer


class PathPopulationAnalyzer:
    """Analyzes population exposure along different drone paths"""
    
    def __init__(self):
        self.data_loader = None
        self.visualizer = None
        self.results = {}
        
    def initialize(self):
        """Load geospatial data"""
        print("Loading geospatial data...")
        self.data_loader = geodata(
            "kimDroneGoon/datasets/worldpopHK/hkg_ppp_2020_UNadj_constrained.tif",
            "kimDroneGoon/datasets/LUMHK_RasterGrid_2024/BLU.tif",
            "kimDroneGoon/datasets/sandboxZones/map.geojson"
        )
        self.visualizer = visualizer(self.data_loader)
        print("✓ Data loaded successfully")
    
    def get_cells_intersected_by_line(self, lat1, lng1, lat2, lng2, buffer_m=50):
        """
        Find all raster cells that the line crosses.
        Uses a buffered line to ensure we capture all cells the path touches.
        
        Args:
            lat1, lng1: Start point (lat/lng)
            lat2, lng2: End point (lat/lng)
            buffer_m: Buffer around line in meters to catch cells (default 50m)
            
        Returns:
            list of population values from all cells the line crosses
        """
        # Create line geometry
        line = LineString([(lng1, lat1), (lng2, lat2)])
        
        # Buffer in degrees (approximate: 1 degree ~ 111 km)
        buffer_deg = (buffer_m / 111000.0)
        buffered_line = line.buffer(buffer_deg)
        
        # Get raster data
        pop_raster = self.data_loader.popRaster
        pop_data = pop_raster.read(1)
        transform = pop_raster.transform
        
        # Convert geometry to raster coordinates
        rows, cols = rasterio.features.geometry_mask(
            [buffered_line.__geo_interface__],
            out_shape=pop_data.shape,
            transform=transform,
            invert=True
        ).nonzero()
        
        # Get population values for all intersecting cells
        populations = []
        for r, c in zip(rows, cols):
            val = float(pop_data[r, c])
            if val > 0:  # Only count positive population
                populations.append(val)
        
        return populations
    
    def _haversine_distance(self, lat1, lng1, lat2, lng2):
        """Calculate great-circle distance in km"""
        R = 6371  # Earth radius in km
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)
        
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    
    def analyze_straight_path(self, waypoints, path_name="PATH"):
        """
        Analyze TOTAL POPULATION under straight paths (direct lines between waypoints).
        Finds ALL 100m cells the path line crosses and sums their population.
        
        Args:
            waypoints: List of (lat, lng) tuples
            path_name: Name for logging
            
        Returns:
            dict with analysis results
        """
        print(f"\n[{path_name}] Analyzing population UNDER path lines...")
        
        total_pop_all_legs = 0
        total_cells = 0
        all_cells_pop = []
        leg_details = []
        
        for i in range(len(waypoints) - 1):
            lat1, lng1 = waypoints[i]
            lat2, lng2 = waypoints[i + 1]
            
            print(f"  Leg {i} -> {i+1}: Getting all cells intersected by line...", end=" ", flush=True)
            
            # Get ALL cells the line intersects
            cell_populations = self.get_cells_intersected_by_line(lat1, lng1, lat2, lng2, buffer_m=50)
            
            distance = self._haversine_distance(lat1, lng1, lat2, lng2)
            total_pop = sum(cell_populations)
            num_cells = len(cell_populations)
            avg_pop = np.mean(cell_populations) if cell_populations else 0
            
            total_pop_all_legs += total_pop
            total_cells += num_cells
            all_cells_pop.extend(cell_populations)
            
            print(f"✓ {num_cells} cells, {int(total_pop)} people")
            
            leg_details.append({
                'leg': f"{i} -> {i+1}",
                'distance_km': round(distance, 3),
                'cells_crossed': num_cells,
                'total_population': int(total_pop),
                'avg_population_per_cell': round(avg_pop, 2)
            })
        
        # Return to start
        if len(waypoints) > 1:
            lat1, lng1 = waypoints[-1]
            lat2, lng2 = waypoints[0]
            
            print(f"  Leg {len(waypoints)-1} -> 0 (return): Getting cells...", end=" ", flush=True)
            
            cell_populations = self.get_cells_intersected_by_line(lat1, lng1, lat2, lng2, buffer_m=50)
            
            distance = self._haversine_distance(lat1, lng1, lat2, lng2)
            total_pop = sum(cell_populations)
            num_cells = len(cell_populations)
            avg_pop = np.mean(cell_populations) if cell_populations else 0
            
            total_pop_all_legs += total_pop
            total_cells += num_cells
            all_cells_pop.extend(cell_populations)
            
            print(f"✓ {num_cells} cells, {int(total_pop)} people")
            
            leg_details.append({
                'leg': f"{len(waypoints)-1} -> 0 (return)",
                'distance_km': round(distance, 3),
                'cells_crossed': num_cells,
                'total_population': int(total_pop),
                'avg_population_per_cell': round(avg_pop, 2)
            })
        
        overall_avg = np.mean(all_cells_pop) if all_cells_pop else 0
        overall_median = np.median(all_cells_pop) if all_cells_pop else 0
        
        return {
            'path_type': path_name,
            'total_population_under_path': int(total_pop_all_legs),
            'total_cells_crossed': total_cells,
            'average_population_per_100m_cell': round(overall_avg, 2),
            'median_population_per_100m_cell': round(overall_median, 2),
            'leg_details': leg_details
        }
    
    def analyze_waypoints_path(self, waypoints_csv):
        """
        Analyze population for paths defined in waypoints CSV.
        
        Args:
            waypoints_csv: Path to CSV file with waypoints
            
        Returns:
            dict with analysis results
        """
        print(f"\n[WAYPOINTS-CSV] Loading waypoints from {waypoints_csv}...")
        
        # Load waypoints from CSV
        try:
            df = pd.read_csv(waypoints_csv)
            waypoints = list(zip(df['latitude'], df['longitude']))
            print(f"  Loaded {len(waypoints)} waypoints from CSV")
        except Exception as e:
            print(f"Error loading waypoints: {e}")
            return None
        
        # Analyze the sequence as-is from CSV
        result = self.analyze_straight_path(waypoints, path_name="STRAIGHT_ORIGINAL_WAYPOINTS")
        
        return result
    
    def get_optimized_route(self):
        """Get the TSP-optimized route from visualizer"""
        print("\n[TSP] Generating TSP-optimized route...")
        route_gdf = self.visualizer.getOptimizedDronePath()
        
        if route_gdf is None or len(route_gdf) < 2:
            print("Could not generate optimized route")
            return None
        
        waypoints = [(row.geometry.y, row.geometry.x) for _, row in route_gdf.iterrows()]
        print(f"  Generated {len(waypoints)} waypoints via TSP optimization")
        return waypoints
    
    def save_results(self, results, output_file='path_population_summary.csv'):
        """Save analysis results to CSV"""
        print(f"\nSaving summary to {output_file}...")
        
        rows = []
        for path_type, data in results.items():
            if data:
                rows.append({
                    'path_type': data['path_type'],
                    'total_population_under_path': data['total_population_under_path'],
                    'total_cells_crossed': data['total_cells_crossed'],
                    'average_population_per_100m_cell': data['average_population_per_100m_cell'],
                    'median_population_per_100m_cell': data['median_population_per_100m_cell']
                })
        
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_file, index=False)
            print(f"✓ Saved to {output_file}")
            return df
        
        return None
    
    def save_detailed_results(self, results, output_file='path_population_detailed.json'):
        """Save detailed results to JSON"""
        print(f"Saving detailed leg-by-leg analysis to {output_file}...")
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"✓ Saved to {output_file}")
    
    def run_complete_analysis(self):
        """Run complete population analysis for all path types"""
        self.initialize()
        
        results = {}
        
        # 1. Analyze waypoints from CSV as STRAIGHT paths
        if Path('drone_mission_waypoints.csv').exists():
            csv_result = self.analyze_waypoints_path('drone_mission_waypoints.csv')
            if csv_result:
                results[csv_result['path_type']] = csv_result
        
        # 2. Generate and analyze TSP-optimized route
        opt_waypoints = self.get_optimized_route()
        if opt_waypoints:
            opt_result = self.analyze_straight_path(opt_waypoints, path_name="OPTIMIZED_TSP_ROUTE")
            results[opt_result['path_type']] = opt_result
        
        # Save results
        df_summary = self.save_results(results)
        self.save_detailed_results(results)
        
        # Print summary
        print("\n" + "="*80)
        print("DRONE PATH POPULATION ANALYSIS SUMMARY")
        print("="*80)
        
        for path_type, data in results.items():
            if data:
                print(f"\n{path_type}:")
                print(f"  ► TOTAL POPULATION UNDER PATH: {data['total_population_under_path']:,} people")
                print(f"  ► CELLS CROSSED: {data['total_cells_crossed']} (100m × 100m cells)")
                print(f"  ► AVG PER 100M SQUARE: {data['average_population_per_100m_cell']} people")
                print(f"  ► MEDIAN PER 100M SQUARE: {data['median_population_per_100m_cell']} people")
                print(f"\n  Leg-by-leg breakdown:")
                for leg in data['leg_details']:
                    print(f"    Leg {leg['leg']}: {leg['cells_crossed']} cells, "
                          f"{leg['total_population']:,} people, "
                          f"{leg['avg_population_per_cell']:.1f} avg/cell")
        
        print("\n" + "="*80)
        return results


if __name__ == '__main__':
    analyzer = PathPopulationAnalyzer()
    results = analyzer.run_complete_analysis()

