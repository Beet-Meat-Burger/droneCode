"""
Population-Aware Curved Routing

Instead of straight-line waypoints, curves routes around high-population areas
to reduce cumulative casualty risk along the flight path.

This is similar to real flight corridor planning - balance distance vs. safety.
"""

import numpy as np
import math
from shapely.geometry import LineString, Point
import geopandas as gpd
from scipy.interpolate import UnivariateSpline


class CurvedRouteOptimizer:
    """
    Optimizes drone routes by curving around high-population density areas.
    """
    
    def __init__(self, geo_loader, altitude_ft=250):
        """
        Args:
            geo_loader: GeometryData loader with population raster
            altitude_ft: Flight altitude for risk calculations
        """
        self.geo_loader = geo_loader
        self.altitude_ft = altitude_ft
    
    def get_population_along_line(self, start_lat, start_lng, end_lat, end_lng, num_samples=20):
        """
        Samples population density along a straight line between two waypoints.
        
        Returns:
            List of (lat, lng, population_density) tuples
        """
        samples = []
        
        for i in range(num_samples):
            t = i / (num_samples - 1)
            
            # Linear interpolation
            lat = start_lat + t * (end_lat - start_lat)
            lng = start_lng + t * (end_lng - start_lng)
            
            # Get population at this point
            try:
                pop = self.geo_loader.getPopulationDensity(lat, lng)
            except:
                pop = 0.0
            
            samples.append({
                'lat': lat,
                'lng': lng,
                'population': pop,
                't': t  # Parameter along line
            })
        
        return samples
    
    def compute_path_casualty_exposure(self, waypoint_path, altitude_ft, num_samples=20):
        """
        Computes total casualty exposure along a route (straight-line segments).
        
        Casualty exposure = integral of (population × death_probability) along path
        
        Args:
            waypoint_path: List of (lat, lng) tuples
            altitude_ft: Flight altitude
            num_samples: Number of intermediate points to sample per segment
            
        Returns:
            Total casualty exposure (unitless metric, higher = riskier)
        """
        total_exposure = 0.0
        
        # Kinetic energy at this altitude (approximation)
        ke = 500 + altitude_ft * 0.5  # Simple linear model
        
        # Death probability
        if ke < 500:
            prob_death = 0.05
        elif ke < 1000:
            prob_death = 0.05 + (0.45 * (ke - 500) / 500)
        else:
            prob_death = min(0.95, 0.50 + (0.45 * (ke - 1000) / 5000))
        
        # Sample along each segment
        for i in range(len(waypoint_path) - 1):
            start_lat, start_lng = waypoint_path[i]
            end_lat, end_lng = waypoint_path[i + 1]
            
            samples = self.get_population_along_line(start_lat, start_lng, end_lat, end_lng, num_samples)
            
            for sample in samples:
                pop = sample['population']
                
                # Population density to people/m² 
                people_per_m2 = pop / 10000.0  # Assuming pop is per 100m cell
                
                # Exposure at this point
                exposure = people_per_m2 * prob_death
                total_exposure += exposure
        
        return total_exposure
    
    def generate_curved_waypoint(self, start_lat, start_lng, end_lat, end_lng, 
                                 curve_factor=0.1):
        """
        Generates a curved path from start to end that avoids high-population areas.
        
        Uses a perpendicular offset based on maximum population density along the line.
        
        Args:
            start_lat, start_lng: Starting point
            end_lat, end_lng: Ending point
            curve_factor: How much to curve (0.0 = straight, higher = more curving)
            
        Returns:
            List of intermediate waypoints [(lat, lng), ...] for curved path
        """
        samples = self.get_population_along_line(start_lat, start_lng, end_lat, end_lng, 20)
        
        # Find point of maximum population density
        max_pop = max(s['population'] for s in samples)
        
        if max_pop < 1.0:  # Low population, don't curve much
            return [(start_lat, start_lng), (end_lat, end_lng)]
        
        # Find midpoint and population at midpoint
        mid_point = samples[len(samples) // 2]
        mid_lat, mid_lng = mid_point['lat'], mid_point['lng']
        mid_pop = mid_point['population']
        
        # Calculate perpendicular offset
        # Direction vector from start to end
        dlat = end_lat - start_lat
        dlng = end_lng - start_lng
        
        # Perpendicular vector (rotate 90 degrees)
        perp_lat = -dlng
        perp_lng = dlat
        
        # Normalize
        length = math.sqrt(perp_lat**2 + perp_lng**2)
        if length > 0:
            perp_lat /= length
            perp_lng /= length
        
        # Offset magnitude based on population density
        # Normalize curve factor based on population (0-100 people/cell)
        normalized_pop = min(1.0, mid_pop / 100.0)
        offset = normalized_pop * curve_factor
        
        # Apply offset to midpoint
        curved_lat = mid_lat + perp_lat * offset
        curved_lng = mid_lng + perp_lng * offset
        
        # Return 3-point path (start, curve point, end)
        return [
            (start_lat, start_lng),
            (curved_lat, curved_lng),
            (end_lat, end_lng)
        ]
    
    def generate_multi_curved_path(self, waypoint_path, curve_factor=0.1, num_intermediate=3):
        """
        Generates a curved route that curves around high-population areas.
        
        Creates multiple intermediate waypoints along the path to avoid population centers.
        
        Args:
            waypoint_path: List of original waypoints [(lat, lng), ...]
            curve_factor: Intensity of curving (0.05 to 0.2 typical)
            num_intermediate: Number of intermediate points per segment
            
        Returns:
            List of curved waypoints
        """
        curved_path = []
        curved_path.append(waypoint_path[0])  # Start at first waypoint
        
        for i in range(len(waypoint_path) - 1):
            start = waypoint_path[i]
            end = waypoint_path[i + 1]
            
            # Generate curved segment
            segment = self.generate_curved_waypoint(
                start[0], start[1], end[0], end[1], curve_factor
            )
            
            # Add intermediate waypoints (skip first since we already added it)
            curved_path.extend(segment[1:-1])
        
        # Add final waypoint
        curved_path.append(waypoint_path[-1])
        
        return curved_path
    
    def compare_straight_vs_curved(self, waypoint_path, curve_factor=0.1):
        """
        Compares casualty exposure of straight vs. curved paths.
        
        Returns:
            Dict with metrics for both approaches
        """
        # Straight line exposure
        straight_exposure = self.compute_path_casualty_exposure(waypoint_path, self.altitude_ft)
        
        # Straight line distance
        straight_distance = 0.0
        for i in range(len(waypoint_path) - 1):
            lat1, lng1 = waypoint_path[i]
            lat2, lng2 = waypoint_path[i + 1]
            # Simple Euclidean distance (degrees to meters: ~111km per degree)
            dist = math.sqrt((lat2 - lat1)**2 + (lng2 - lng1)**2) * 111_000
            straight_distance += dist
        
        # Curved path
        curved_path = self.generate_multi_curved_path(waypoint_path, curve_factor)
        curved_exposure = self.compute_path_casualty_exposure(curved_path, self.altitude_ft)
        
        # Curved path distance
        curved_distance = 0.0
        for i in range(len(curved_path) - 1):
            lat1, lng1 = curved_path[i]
            lat2, lng2 = curved_path[i + 1]
            dist = math.sqrt((lat2 - lat1)**2 + (lng2 - lng1)**2) * 111_000
            curved_distance += dist
        
        return {
            'straight_waypoints': waypoint_path,
            'straight_exposure': straight_exposure,
            'straight_distance_m': straight_distance,
            'straight_distance_km': straight_distance / 1000.0,
            
            'curved_waypoints': curved_path,
            'curved_exposure': curved_exposure,
            'curved_distance_m': curved_distance,
            'curved_distance_km': curved_distance / 1000.0,
            
            'exposure_reduction_pct': ((straight_exposure - curved_exposure) / straight_exposure * 100) if straight_exposure > 0 else 0,
            'distance_increase_pct': ((curved_distance - straight_distance) / straight_distance * 100) if straight_distance > 0 else 0,
            'exposure_per_km_straight': (straight_exposure / straight_distance * 1000) if straight_distance > 0 else 0,
            'exposure_per_km_curved': (curved_exposure / curved_distance * 1000) if curved_distance > 0 else 0
        }
    
    def print_comparison(self, comparison, compat_ft=None):
        """Pretty-prints straight vs. curved comparison."""
        if compat_ft is None:
            alt_str = f"{self.altitude_ft}ft"
        else:
            alt_str = f"{compat_ft}ft"
        
        print("\n" + "="*70)
        print(f"STRAIGHT VS. CURVED ROUTE ANALYSIS ({alt_str})")
        print("="*70)
        
        print(f"\nSTRAIGHT PATH:")
        print(f"  Distance: {comparison['straight_distance_km']:.2f} km")
        print(f"  Casualty Exposure: {comparison['straight_exposure']:.4f}")
        print(f"  Exposure/km: {comparison['exposure_per_km_straight']:.6f}")
        print(f"  Waypoints: {len(comparison['straight_waypoints'])}")
        
        print(f"\nCURVED PATH:")
        print(f"  Distance: {comparison['curved_distance_km']:.2f} km")
        print(f"  Casualty Exposure: {comparison['curved_exposure']:.4f}")
        print(f"  Exposure/km: {comparison['exposure_per_km_curved']:.6f}")
        print(f"  Waypoints: {len(comparison['curved_waypoints'])}")
        
        print(f"\nTRADE-OFFS:")
        print(f"  Exposure Reduction: {comparison['exposure_reduction_pct']:.1f}%")
        print(f"  Distance Increase: {comparison['distance_increase_pct']:.1f}%")
        
        # Decision logic
        if comparison['exposure_reduction_pct'] > 10 and comparison['distance_increase_pct'] < 5:
            rec = "✓ RECOMMEND CURVED (good risk reduction, minimal distance increase)"
        elif comparison['exposure_reduction_pct'] > 5:
            rec = "~ CONSIDER CURVED (moderate trade-off)"
        else:
            rec = "✗ STICK WITH STRAIGHT (not enough risk reduction to justify extra distance)"
        
        print(f"\nRECOMMENDATION:")
        print(f"  {rec}")
        
        print("="*70 + "\n")


def analyze_population_avoidance_value(geo_loader, waypoint_gdf):
    """
    Analyzes whether curved routing is worthwhile for this specific route.
    """
    print("\n" + "="*70)
    print("POPULATION AVOIDANCE ANALYSIS")
    print("="*70)
    
    optimizer = CurvedRouteOptimizer(geo_loader, altitude_ft=250)
    
    # Extract waypoints
    waypoint_path = [(row.geometry.y, row.geometry.x) for _, row in waypoint_gdf.iterrows()]
    
    if len(waypoint_path) < 2:
        print("[!] Need at least 2 waypoints")
        return
    
    # Analyze different curve intensities
    print(f"\n[*] Analyzing {len(waypoint_path)} waypoints with different curve intensities...")
    
    curve_factors = [0.0, 0.05, 0.10, 0.15, 0.20]
    results = {}
    
    for curve_factor in curve_factors:
        if curve_factor == 0.0:
            # Straight line case
            exposure = optimizer.compute_path_casualty_exposure(waypoint_path, 250)
            results[curve_factor] = {
                'exposure': exposure,
                'distance_km': sum(
                    math.sqrt((waypoint_path[i+1][0] - waypoint_path[i][0])**2 + 
                             (waypoint_path[i+1][1] - waypoint_path[i][1])**2) * 111
                    for i in range(len(waypoint_path) - 1)
                )
            }
        else:
            comparison = optimizer.compare_straight_vs_curved(waypoint_path, curve_factor)
            results[curve_factor] = {
                'exposure': comparison['curved_exposure'],
                'distance_km': comparison['curved_distance_km'],
                'exposure_reduction_pct': comparison['exposure_reduction_pct'],
                'distance_increase_pct': comparison['distance_increase_pct']
            }
    
    # Print summary table
    print(f"\n{'Curve':<10} {'Exposure':<15} {'Distance':<12} {'Risk Red.':<12} {'Dist Inc.':<12}")
    print("-"*70)
    
    straight_exposure = results[0.0]['exposure']
    straight_distance = results[0.0]['distance_km']
    
    for curve_factor in curve_factors:
        result = results[curve_factor]
        exp = result['exposure']
        dist = result['distance_km']
        
        if curve_factor == 0.0:
            print(f"STRAIGHT  {exp:<15.4f} {dist:<12.2f} baseline    baseline")
        else:
            exp_red = ((straight_exposure - exp) / straight_exposure * 100) if straight_exposure > 0 else 0
            dist_inc = ((dist - straight_distance) / straight_distance * 100) if straight_distance > 0 else 0
            print(f"{curve_factor:<10.2f} {exp:<15.4f} {dist:<12.2f} {exp_red:<12.1f}% {dist_inc:<12.1f}%")
    
    # Recommendation
    print(f"\n[*] CONCLUSION:")
    
    best_curve = None
    best_ratio = 0
    
    for cf in curve_factors[1:]:
        result = results[cf]
        if straight_exposure > result['exposure']:
            # Calculate efficiency: risk reduction per distance increase
            ratio = result['exposure_reduction_pct'] / max(0.1, result['distance_increase_pct'])
            if ratio > best_ratio:
                best_ratio = ratio
                best_curve = cf
    
    if best_curve is not None:
        result = results[best_curve]
        print(f"  ✓ YES, curved routing is worthwhile!")
        print(f"  → Recommended curve factor: {best_curve}")
        print(f"  → Risk reduction: {result['exposure_reduction_pct']:.1f}%")
        print(f"  → Extra distance: {result['distance_increase_pct']:.1f}%")
        print(f"  → Efficiency ratio: {best_ratio:.2f}")
    else:
        print(f"  ✗ NO, population density too low to justify curved routing")
        print(f"  → Stick with straight paths for maximum efficiency")
    
    print("="*70 + "\n")
    
    return results


if __name__ == '__main__':
    print("Population-Aware Curved Routing Module")
    print("Use with optimize_pathfinding.py to enhance routes")
