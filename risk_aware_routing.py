"""
Risk-Aware Drone Pathfinding

Integrates casualty risk metrics into TSP routing optimization.
Uses altitude-dependent kinetic energy and population density to compute safe flight paths.
"""

import numpy as np
import math
from kimDroneGoon.simulation import DroneSimulator


class RiskAwareRouter:
    """
    Extends TSP routing to include casualty risk as a cost factor.
    """
    
    def __init__(self, simulator, altitude_stats):
        """
        Args:
            simulator: DroneSimulator instance
            altitude_stats: Dict from altitude_analysis.py containing KE and death prob by altitude
        """
        self.simulator = simulator
        self.altitude_stats = altitude_stats
        self.drone = simulator.drone
        
    def get_kinetic_energy_at_altitude(self, altitude_ft):
        """
        Returns KE for a given altitude from precomputed stats.
        Interpolates if altitude not in stats.
        """
        if altitude_ft in self.altitude_stats:
            return self.altitude_stats[altitude_ft]['avg_kinetic_energy_j']
        
        # Linear interpolation
        sorted_alts = sorted(self.altitude_stats.keys())
        if altitude_ft < sorted_alts[0]:
            return self.altitude_stats[sorted_alts[0]]['avg_kinetic_energy_j']
        if altitude_ft > sorted_alts[-1]:
            return self.altitude_stats[sorted_alts[-1]]['avg_kinetic_energy_j']
        
        # Find surrounding altitudes
        for i in range(len(sorted_alts) - 1):
            if sorted_alts[i] <= altitude_ft <= sorted_alts[i+1]:
                alt1, alt2 = sorted_alts[i], sorted_alts[i+1]
                ke1 = self.altitude_stats[alt1]['avg_kinetic_energy_j']
                ke2 = self.altitude_stats[alt2]['avg_kinetic_energy_j']
                
                # Linear interpolation
                t = (altitude_ft - alt1) / (alt2 - alt1)
                return ke1 + t * (ke2 - ke1)
        
        return self.altitude_stats[sorted_alts[-1]]['avg_kinetic_energy_j']
    
    def get_death_probability(self, kinetic_energy_j):
        """
        Returns death probability for given kinetic energy.
        """
        if kinetic_energy_j < 500:
            prob_death = 0.05
        elif kinetic_energy_j < 1000:
            prob_death = 0.05 + (0.45 * (kinetic_energy_j - 500) / 500)
        else:
            prob_death = 0.50 + (0.45 * (kinetic_energy_j - 1000) / 5000)
            prob_death = min(0.95, prob_death)
        
        return prob_death
    
    def compute_casualty_probability(self, population_density, altitude_ft):
        """
        Computes casualty probability for a waypoint given:
        - Population density (people per cell)
        - Flight altitude
        
        Returns float in [0, 1]
        """
        # Get KE at this altitude
        ke = self.get_kinetic_energy_at_altitude(altitude_ft)
        
        # Get death probability
        prob_death = self.get_death_probability(ke)
        
        # Population: convert from people/cell to people/m²
        cell_area_m2 = 10000  # 100m x 100m
        people_per_m2 = population_density / cell_area_m2
        
        # Impact area = 1 m²
        expected_people = people_per_m2 * 1.0
        
        # Probability of hit
        prob_hit = min(1.0, expected_people)
        
        # Casualty probability
        prob_casualty = prob_hit * prob_death
        
        return prob_casualty
    
    def compute_risk_weighted_cost(self, distance_m, pop_density, altitude_ft, 
                                    distance_weight=1.0, risk_weight=1000.0):
        """
        Combines distance and casualty risk into a single cost metric.
        
        Args:
            distance_m: Physical distance between waypoints (meters)
            pop_density: Population density (people per cell)
            altitude_ft: Flight altitude (feet)
            distance_weight: Weight for distance term (default 1.0)
            risk_weight: Scale factor for risk term (default 1000.0)
            
        Returns:
            Weighted cost (higher = worse)
        """
        # Distance term (normalized, in km)
        distance_cost = (distance_m / 1000.0) * distance_weight
        
        # Risk term (casualty probability scaled)
        casualty_prob = self.compute_casualty_probability(pop_density, altitude_ft)
        risk_cost = casualty_prob * risk_weight
        
        # Combined cost
        total_cost = distance_cost + risk_cost
        
        return total_cost
    
    def generate_altitude_profile(self, waypoint_gdf, strategy='mixed'):
        """
        Generates altitude recommendations for each waypoint.
        
        Strategies:
        - 'low': Always use low altitude (safest for impact energy)
        - 'high': Always use high altitude (faster, avoids low-alt congestion)
        - 'mixed': Low altitude over populated areas, high over sparse areas
        - 'optimal': Choose altitude that minimizes risk for each waypoint
        
        Args:
            waypoint_gdf: GeoDataFrame with 'pop' column (population density)
            strategy: Altitude selection strategy
            
        Returns:
            List of altitudes (feet) for each waypoint
        """
        altitudes = []
        
        # Safe altitude thresholds
        low_alt = 100  # ft (slow, low energy)
        high_alt = 500  # ft (fast, high energy)
        mixed_threshold = 50  # people/cell (switch point)
        
        for _, row in waypoint_gdf.iterrows():
            pop = row.get('pop', 0)
            
            if strategy == 'low':
                altitudes.append(low_alt)
            
            elif strategy == 'high':
                altitudes.append(high_alt)
            
            elif strategy == 'mixed':
                # Low altitude in populated areas, high in sparse
                if pop > mixed_threshold:
                    altitudes.append(low_alt)
                else:
                    altitudes.append(high_alt)
            
            elif strategy == 'optimal':
                # Choose altitude that minimizes casualty probability
                # Compare low vs high or midpoint
                risk_low = self.compute_casualty_probability(pop, low_alt)
                risk_high = self.compute_casualty_probability(pop, high_alt)
                
                # Pick the lower-risk altitude
                if risk_low <= risk_high:
                    altitudes.append(low_alt)
                else:
                    altitudes.append(high_alt)
        
        return altitudes
    
    def generate_risk_report(self, waypoint_gdf, altitude_profile):
        """
        Generates a detailed risk report for a planned flight.
        
        Args:
            waypoint_gdf: GeoDataFrame with waypoints and population
            altitude_profile: List of altitudes (feet) for each waypoint
            
        Returns:
            Report dict with casualty statistics
        """
        report = {
            'num_waypoints': len(waypoint_gdf),
            'waypoint_risks': [],
            'total_casualty_probability': 0.0,
            'max_casualty_probability': 0.0,
            'high_risk_waypoints': []
        }
        
        for idx, (_, row) in enumerate(waypoint_gdf.iterrows()):
            pop = row.get('pop', 0)
            altitude_ft = altitude_profile[idx] if idx < len(altitude_profile) else 250
            
            # Compute risk at this waypoint
            casualty_prob = self.compute_casualty_probability(pop, altitude_ft)
            ke = self.get_kinetic_energy_at_altitude(altitude_ft)
            death_prob = self.get_death_probability(ke)
            
            waypoint_info = {
                'waypoint_id': idx,
                'population': pop,
                'altitude_ft': altitude_ft,
                'kinetic_energy_j': ke,
                'death_probability': death_prob,
                'casualty_probability': casualty_prob
            }
            
            report['waypoint_risks'].append(waypoint_info)
            report['total_casualty_probability'] += casualty_prob
            
            if casualty_prob > report['max_casualty_probability']:
                report['max_casualty_probability'] = casualty_prob
            
            # Flag high-risk waypoints (>5% casualty probability)
            if casualty_prob > 0.05:
                report['high_risk_waypoints'].append(idx)
        
        # Compute average risk
        report['avg_casualty_probability'] = report['total_casualty_probability'] / len(waypoint_gdf) if waypoint_gdf else 0
        
        return report
    
    def print_risk_report(self, report, strategy_name='Unknown'):
        """Pretty-prints a risk report."""
        print("\n" + "="*70)
        print(f"RISK ASSESSMENT REPORT: {strategy_name} Strategy")
        print("="*70)
        print(f"\nTotal Waypoints: {report['num_waypoints']}")
        print(f"  High-Risk Waypoints (>5%): {len(report['high_risk_waypoints'])}")
        
        print(f"\nCasualty Probability Stats:")
        print(f"  Total (summed): {report['total_casualty_probability']:.4f}")
        print(f"  Average per waypoint: {report['avg_casualty_probability']:.6f}")
        print(f"  Maximum: {report['max_casualty_probability']:.4f}")
        
        if report['high_risk_waypoints']:
            print(f"\nHigh-Risk Waypoint Details:")
            for wp_id in report['high_risk_waypoints'][:5]:  # Show top 5
                wp = report['waypoint_risks'][wp_id]
                print(f"  Waypoint {wp_id}: Pop={wp['population']:.0f}, "
                      f"Alt={wp['altitude_ft']:.0f}ft, "
                      f"KE={wp['kinetic_energy_j']:.0f}J, "
                      f"Casualty Risk={wp['casualty_probability']*100:.2f}%")
        
        print("="*70 + "\n")


def compare_routing_strategies(simulator, alt_stats, waypoint_gdf):
    """
    Compares different altitude-aware routing strategies.
    """
    router = RiskAwareRouter(simulator, alt_stats)
    
    strategies = ['low', 'high', 'mixed', 'optimal']
    results = {}
    
    print("\n" + "="*70)
    print("COMPARING ALTITUDE-AWARE ROUTING STRATEGIES")
    print("="*70)
    
    for strategy in strategies:
        print(f"\n>>> Evaluating '{strategy}' strategy...")
        
        # Generate altitude profile
        altitude_profile = router.generate_altitude_profile(waypoint_gdf, strategy)
        
        # Generate risk report
        report = router.generate_risk_report(waypoint_gdf, altitude_profile)
        results[strategy] = report
        
        # Print summary
        router.print_risk_report(report, strategy_name=strategy)
    
    # Summary comparison
    print("\n" + "="*70)
    print("STRATEGY COMPARISON SUMMARY")
    print("="*70)
    print(f"\n{'Strategy':<15} {'Total Risk':<15} {'Max Risk':<15} {'High-Risk WP':<15}")
    print("-"*70)
    
    for strategy in strategies:
        report = results[strategy]
        print(f"{strategy:<15} {report['total_casualty_probability']:<15.4f} "
              f"{report['max_casualty_probability']:<15.4f} {len(report['high_risk_waypoints']):<15}")
    
    print("="*70 + "\n")
    
    return results


if __name__ == '__main__':
    print("Risk-Aware Routing Module")
    print("Use in conjunction with altitude_analysis.py results")
