"""
Waypoint Insertion for Long Legs

Automatically inserts waypoints to break up long flight legs (>10km)
at the lowest population density points to minimize casualty risk.
"""

import math
import numpy as np
from shapely.geometry import Point


class LongLegBreaker:
    """
    Identifies and breaks up long flight legs by inserting waypoints
    at the lowest population spots along the segment.
    """
    
    def __init__(self, geo_loader, max_leg_distance_km=10.0):
        """
        Args:
            geo_loader: GeometryData loader with population raster
            max_leg_distance_km: Maximum allowable leg distance (default 10 km)
        """
        self.geo_loader = geo_loader
        self.max_leg_distance_km = max_leg_distance_km
        self.max_leg_distance_m = max_leg_distance_km * 1000
    
    def haversine_distance(self, lat1, lng1, lat2, lng2):
        """
        Calculates great-circle distance in meters between two points.
        """
        R = 6371000  # Earth radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)
        
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def sample_points_along_leg(self, start_lat, start_lng, end_lat, end_lng, num_samples=50):
        """
        Generates sample points along a leg with their population densities.
        
        Returns:
            List of dicts: {'lat': lat, 'lng': lng, 'population': pop, 't': t}
        """
        samples = []
        
        for i in range(num_samples):
            t = i / (num_samples - 1)
            
            # Linear interpolation
            lat = start_lat + t * (end_lat - start_lat)
            lng = start_lng + t * (end_lng - start_lng)
            
            # Get population
            try:
                pop = self.geo_loader.getPopulationDensity(lat, lng)
            except:
                pop = 0.0
            
            samples.append({
                'lat': lat,
                'lng': lng,
                'population': pop,
                't': t
            })
        
        return samples
    
    def find_lowest_population_points(self, leg_samples, num_points=1):
        """
        Finds the lowest population points at evenly-spaced middle positions along a leg.
        
        Args:
            leg_samples: List of sampled points with population
            num_points: How many insertion points to find
            
        Returns:
            List of (lat, lng) tuples at middle positions with lowest nearby population
        """
        # Calculate target positions: evenly space waypoints along the leg
        # For N waypoints to insert, place at positions 1/(N+1), 2/(N+1), ..., N/(N+1)
        target_positions = [(i+1) / (num_points + 1) for i in range(num_points)]
        
        insertion_points = []
        search_radius = 0.15  # Look within ±15% of leg length around target position
        
        for target_t in target_positions:
            # Find samples near this target position
            nearby_samples = [
                s for s in leg_samples 
                if abs(s['t'] - target_t) <= search_radius
            ]
            
            if nearby_samples:
                # Among nearby samples, pick the one with lowest population
                best_point = min(nearby_samples, key=lambda x: x['population'])
                insertion_points.append(best_point)
            else:
                # Fallback: if no samples nearby, find closest to target position
                best_point = min(leg_samples, key=lambda x: abs(x['t'] - target_t))
                insertion_points.append(best_point)
        
        # Sort by position along leg for insertion order
        insertion_points = sorted(insertion_points, key=lambda x: x['t'])
        
        return [(p['lat'], p['lng']) for p in insertion_points]
    
    def break_long_legs(self, waypoint_gdf):
        """
        Takes a GeoDataFrame of waypoints and inserts new waypoints
        to break up any legs longer than max_leg_distance_km.
        
        Args:
            waypoint_gdf: GeoDataFrame with geometry and 'pop' column
            
        Returns:
            List of (lat, lng) tuples with inserted waypoints
        """
        # Extract waypoints
        waypoints = [(row.geometry.y, row.geometry.x) for _, row in waypoint_gdf.iterrows()]
        
        result_waypoints = []
        leg_info = []
        
        print(f"\n[*] Breaking long legs (max: {self.max_leg_distance_km} km)...")
        
        for i in range(len(waypoints)):
            result_waypoints.append(waypoints[i])
            
            if i < len(waypoints) - 1:
                start_lat, start_lng = waypoints[i]
                end_lat, end_lng = waypoints[i + 1]
                
                # Calculate leg distance
                leg_distance_m = self.haversine_distance(start_lat, start_lng, end_lat, end_lng)
                leg_distance_km = leg_distance_m / 1000.0
                
                # Check if leg needs breaking
                if leg_distance_km > self.max_leg_distance_km:
                    print(f"\n  Leg {i} → {i+1}: {leg_distance_km:.2f} km (too long!)")
                    
                    # Calculate how many intermediate points needed
                    num_intermediate = math.ceil(leg_distance_km / self.max_leg_distance_km) - 1
                    print(f"    → Need {num_intermediate} intermediate waypoint(s)")
                    
                    # Sample population along leg
                    samples = self.sample_points_along_leg(start_lat, start_lng, end_lat, end_lng, 100)
                    
                    # Find lowest population points
                    insertion_points = self.find_lowest_population_points(samples, num_intermediate)
                    
                    # Add insertion points to result
                    for ins_lat, ins_lng in insertion_points:
                        # Get population density at insertion point
                        try:
                            ins_pop = self.geo_loader.getPopulationDensity(ins_lat, ins_lng)
                        except:
                            ins_pop = 0.0
                        
                        result_waypoints.append((ins_lat, ins_lng))
                        
                        print(f"      • Inserted at ({ins_lat:.4f}, {ins_lng:.4f}), population: {ins_pop:.0f}")
                    
                    leg_info.append({
                        'original_leg': (i, i+1),
                        'distance_km': leg_distance_km,
                        'intermediate_waypoints': num_intermediate,
                        'insertion_points': insertion_points
                    })
                
                else:
                    print(f"  Leg {i} → {i+1}: {leg_distance_km:.2f} km ✓")
        
        return result_waypoints, leg_info
    
    def print_leg_summary(self, original_waypoints, new_waypoints, leg_info):
        """Pretty-prints leg breaking summary."""
        print("\n" + "="*70)
        print("LEG BREAKING SUMMARY")
        print("="*70)
        
        print(f"\nOriginal route: {len(original_waypoints)} waypoints")
        print(f"Optimized route: {len(new_waypoints)} waypoints")
        print(f"Waypoints added: {len(new_waypoints) - len(original_waypoints)}")
        
        if leg_info:
            print(f"\nLong legs that were broken:")
            total_distance_saved = 0
            for info in leg_info:
                orig_leg = info['original_leg']
                dist = info['distance_km']
                num_intermediate = info['intermediate_waypoints']
                
                # Distance per segment after breaking
                new_segment_length = dist / (num_intermediate + 1)
                
                print(f"  Leg {orig_leg[0]} → {orig_leg[1]}: {dist:.2f} km")
                print(f"    → Split into {num_intermediate + 1} segments of ~{new_segment_length:.2f} km each")
                print(f"    → Inserted {num_intermediate} waypoint(s) at lowest population spots")
        else:
            print(f"\n✓ No legs exceed {self.max_leg_distance_km} km threshold")
        
        print("="*70 + "\n")


def optimize_waypoints_with_leg_breaking(waypoint_gdf, geo_loader, max_leg_km=10.0):
    """
    Convenience function: Takes original waypoints and returns optimized list
    with long legs broken up.
    
    Args:
        waypoint_gdf: GeoDataFrame of waypoints
        geo_loader: GeometryData instance
        max_leg_km: Maximum leg length before breaking
        
    Returns:
        Tuple: (optimized_waypoints_list, leg_info_dict)
    """
    breaker = LongLegBreaker(geo_loader, max_leg_km)
    
    original_waypoints = [(row.geometry.y, row.geometry.x) for _, row in waypoint_gdf.iterrows()]
    new_waypoints, leg_info = breaker.break_long_legs(waypoint_gdf)
    
    breaker.print_leg_summary(original_waypoints, new_waypoints, leg_info)
    
    return new_waypoints, leg_info


if __name__ == '__main__':
    print("Long Leg Breaker Module")
    print("Use to optimize waypoint spacing for drone battery constraints")
