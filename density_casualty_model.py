"""
Density-to-Casualty Model Analysis

Models the relationship between population density and casualty probability.
Shows how density impacts risk at different altitudes.

Useful for:
- Route planning decisions (avoid high-density areas)
- Risk assessment (what density = what risk?)
- Waypoint selection (choose low-density routing)
"""

import numpy as np
import matplotlib.pyplot as plt
import csv
from kimDroneGoon.simulation import DroneSimulator


class DensityToCasualtyModel:
    """
    Maps population density to casualty probability at given altitude(s).
    """
    
    def __init__(self, drone, altitude_stats):
        """
        Args:
            drone: Drone instance (for mass/specs)
            altitude_stats: Dict from altitude_analysis with KE/death prob by altitude
        """
        self.drone = drone
        self.altitude_stats = altitude_stats
        self.IMPACT_AREA_M2 = 1.0  # 1 m² impact zone
    
    def get_death_probability(self, altitude_ft):
        """
        Returns death probability at given altitude from precomputed stats.
        Interpolates if needed.
        """
        if altitude_ft in self.altitude_stats:
            return self.altitude_stats[altitude_ft]['avg_death_probability']
        
        # Linear interpolation
        sorted_alts = sorted(self.altitude_stats.keys())
        if altitude_ft <= sorted_alts[0]:
            return self.altitude_stats[sorted_alts[0]]['avg_death_probability']
        if altitude_ft >= sorted_alts[-1]:
            return self.altitude_stats[sorted_alts[-1]]['avg_death_probability']
        
        for i in range(len(sorted_alts) - 1):
            if sorted_alts[i] <= altitude_ft <= sorted_alts[i+1]:
                alt1, alt2 = sorted_alts[i], sorted_alts[i+1]
                prob1 = self.altitude_stats[alt1]['avg_death_probability']
                prob2 = self.altitude_stats[alt2]['avg_death_probability']
                t = (altitude_ft - alt1) / (alt2 - alt1)
                return prob1 + t * (prob2 - prob1)
        
        return self.altitude_stats[sorted_alts[-1]]['avg_death_probability']
    
    def compute_casualty_probability(self, population_density, altitude_ft):
        """
        Computes casualty probability for given:
        - Population density (people per 100m cell)
        - Altitude (feet)
        
        Returns:
            Casualty probability (float in [0, 1])
        """
        # Get death probability at this altitude
        prob_death = self.get_death_probability(altitude_ft)
        
        # Convert population density to people per m²
        cell_area_m2 = 10000  # 100m × 100m cell
        people_per_m2 = population_density / cell_area_m2
        
        # Expected people in 1 m² impact zone
        expected_people = people_per_m2 * self.IMPACT_AREA_M2
        
        # Probability at least one person is hit (Poisson approximation)
        prob_hit = min(1.0, expected_people)
        
        # Casualty probability
        prob_casualty = prob_hit * prob_death
        
        return prob_casualty
    
    def generate_density_curve(self, altitude_ft, density_range=None, num_points=50):
        """
        Generates casualty probability curve across density spectrum.
        
        Args:
            altitude_ft: Flight altitude
            density_range: (min, max) population density to analyze
            num_points: Number of density points to sample
            
        Returns:
            List of dicts: {'density': dens, 'casualty_prob': prob, ...}
        """
        if density_range is None:
            density_range = (0, 500)  # 0 to 500 people per cell
        
        min_dens, max_dens = density_range
        densities = np.linspace(min_dens, max_dens, num_points)
        
        prob_death = self.get_death_probability(altitude_ft)
        
        curve = []
        for density in densities:
            casualty_prob = self.compute_casualty_probability(density, altitude_ft)
            
            # Also compute expected casualties per 1000 impacts
            expected_casualties_per_1000 = casualty_prob * 1000
            
            curve.append({
                'population_density': density,
                'casualty_probability': casualty_prob,
                'casualty_probability_pct': casualty_prob * 100,
                'expected_casualties_per_1000_impacts': expected_casualties_per_1000,
                'death_probability': prob_death
            })
        
        return curve
    
    def compare_altitudes_by_density(self, density_range=None, num_points=50):
        """
        Compares casualty probability curves for multiple altitudes.
        
        Returns:
            Dict with curves for each altitude
        """
        if density_range is None:
            density_range = (0, 500)
        
        altitudes = sorted(self.altitude_stats.keys())
        curves = {}
        
        for altitude_ft in altitudes:
            curves[altitude_ft] = self.generate_density_curve(altitude_ft, density_range, num_points)
        
        return curves
    
    def export_density_casualty_csv(self, output_file='density_casualty_model.csv'):
        """
        Exports density-to-casualty mapping for all altitudes.
        """
        print(f"\n[*] Generating density-to-casualty model...")
        
        curves = self.compare_altitudes_by_density(density_range=(0, 500), num_points=51)
        
        # Flatten for CSV export
        rows = []
        for altitude_ft in sorted(curves.keys()):
            for point in curves[altitude_ft]:
                rows.append({
                    'altitude_ft': altitude_ft,
                    'population_density': point['population_density'],
                    'death_probability': f"{point['death_probability']:.4f}",
                    'probability_of_hit': min(1.0, point['population_density'] / 10000),
                    'casualty_probability': f"{point['casualty_probability']:.6f}",
                    'casualty_probability_pct': f"{point['casualty_probability_pct']:.4f}",
                    'expected_casualties_per_1000': f"{point['expected_casualties_per_1000_impacts']:.2f}"
                })
        
        # Write CSV
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'altitude_ft', 'population_density', 'death_probability', 'probability_of_hit',
                'casualty_probability', 'casualty_probability_pct', 'expected_casualties_per_1000'
            ])
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"    ✓ Exported to {output_file} ({len(rows)} rows)")
        
        return rows
    
    def generate_density_plots(self, output_file='density_casualty_plot.png'):
        """
        Generates visualization of density-to-casualty relationships.
        """
        print(f"\n[*] Generating visualization...")
        
        altitudes = sorted(self.altitude_stats.keys())
        
        # Generate curves
        density_range = (0, 500)
        curves = {}
        for altitude_ft in altitudes:
            curves[altitude_ft] = self.generate_density_curve(altitude_ft, density_range, 100)
        
        # Create plots
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Population Density → Casualty Probability Model', fontsize=16, fontweight='bold')
        
        # Plot 1: Casualty probability vs density (multiple altitudes)
        ax = axes[0, 0]
        for altitude_ft in altitudes[::max(1, len(altitudes)//4)]:  # Sample 4 altitudes
            densities = [p['population_density'] for p in curves[altitude_ft]]
            probs = [p['casualty_probability_pct'] for p in curves[altitude_ft]]
            ax.plot(densities, probs, marker='o', markersize=3, label=f'{altitude_ft} ft', linewidth=2)
        
        ax.set_xlabel('Population Density (people/100m cell)', fontsize=11)
        ax.set_ylabel('Casualty Probability (%)', fontsize=11)
        ax.set_title('Casualty Probability by Population Density')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Plot 2: Low vs High altitude comparison
        ax = axes[0, 1]
        low_alt = altitudes[0]
        high_alt = altitudes[-1]
        
        low_curve = curves[low_alt]
        high_curve = curves[high_alt]
        
        densities = [p['population_density'] for p in low_curve]
        low_probs = [p['casualty_probability_pct'] for p in low_curve]
        high_probs = [p['casualty_probability_pct'] for p in high_curve]
        
        ax.plot(densities, low_probs, 'g-o', linewidth=2, label=f'{low_alt} ft (Safe)', markersize=4)
        ax.plot(densities, high_probs, 'r-s', linewidth=2, label=f'{high_alt} ft (Risky)', markersize=4)
        ax.fill_between(densities, low_probs, high_probs, alpha=0.2, color='orange')
        
        ax.set_xlabel('Population Density (people/100m cell)', fontsize=11)
        ax.set_ylabel('Casualty Probability (%)', fontsize=11)
        ax.set_title(f'Low vs High Altitude: Risk Difference')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Plot 3: Expected casualties per 1000 impacts
        ax = axes[1, 0]
        for altitude_ft in altitudes[::max(1, len(altitudes)//3)]:
            densities = [p['population_density'] for p in curves[altitude_ft]]
            expected = [p['expected_casualties_per_1000_impacts'] for p in curves[altitude_ft]]
            ax.plot(densities, expected, marker='o', markersize=3, label=f'{altitude_ft} ft', linewidth=2)
        
        ax.set_xlabel('Population Density (people/100m cell)', fontsize=11)
        ax.set_ylabel('Expected Casualties (per 1000 impacts)', fontsize=11)
        ax.set_title('Casualty Scale: Expected Deaths per 1000 Failures')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Plot 4: Risk zones by density
        ax = axes[1, 1]
        
        mid_alt = altitudes[len(altitudes)//2]
        curve = curves[mid_alt]
        densities = [p['population_density'] for p in curve]
        probs = [p['casualty_probability_pct'] for p in curve]
        
        # Color zones by risk level
        colors = []
        for prob in probs:
            if prob < 0.001:
                colors.append('green')
            elif prob < 0.01:
                colors.append('yellow')
            elif prob < 0.05:
                colors.append('orange')
            else:
                colors.append('red')
        
        ax.scatter(densities, probs, c=colors, s=100, alpha=0.6, edgecolors='black')
        
        # Add zone lines
        ax.axhline(y=0.001, color='green', linestyle='--', linewidth=1, alpha=0.5, label='Very Safe')
        ax.axhline(y=0.01, color='yellow', linestyle='--', linewidth=1, alpha=0.5, label='Safe')
        ax.axhline(y=0.05, color='orange', linestyle='--', linewidth=1, alpha=0.5, label='Moderate')
        
        ax.set_xlabel('Population Density (people/100m cell)', fontsize=11)
        ax.set_ylabel('Casualty Probability (%)', fontsize=11)
        ax.set_title(f'Risk Zones at {mid_alt} ft')
        ax.set_yscale('log')
        ax.legend()
        ax.grid(True, alpha=0.3, which='both')
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"    ✓ Saved to {output_file}")
        plt.close()
    
    def print_density_summary(self):
        """
        Prints a summary of density-to-casualty relationships.
        """
        print("\n" + "="*70)
        print("POPULATION DENSITY → CASUALTY PROBABILITY MODEL")
        print("="*70)
        
        altitudes = sorted(self.altitude_stats.keys())
        test_densities = [10, 50, 100, 250, 500]
        
        print(f"\nDensity Thresholds at Different Altitudes:")
        print(f"\n{'Density':<12} ", end='')
        for alt in altitudes[::max(1, len(altitudes)//4)]:
            print(f"{alt}ft      ", end='')
        print()
        print("-"*70)
        
        for density in test_densities:
            print(f"{density:>5} ppl/cell  ", end='')
            for alt in altitudes[::max(1, len(altitudes)//4)]:
                prob = self.compute_casualty_probability(density, alt)
                print(f"{prob*100:>6.3f}%  ", end='')
            print()
        
        print("\n" + "="*70)
        print("INTERPRETATION")
        print("="*70)
        
        low_alt = altitudes[0]
        high_alt = altitudes[-1]
        
        print(f"\nAt low population (10 people/cell):")
        low_prob_low = self.compute_casualty_probability(10, low_alt)
        low_prob_high = self.compute_casualty_probability(10, high_alt)
        print(f"  {low_alt}ft:  {low_prob_low*100:.4f}% risk")
        print(f"  {high_alt}ft: {low_prob_high*100:.4f}% risk (ratio: {low_prob_high/low_prob_low:.1f}x)")
        
        print(f"\nAt high population (500 people/cell):")
        high_prob_low = self.compute_casualty_probability(500, low_alt)
        high_prob_high = self.compute_casualty_probability(500, high_alt)
        print(f"  {low_alt}ft:  {high_prob_low*100:.4f}% risk")
        print(f"  {high_alt}ft: {high_prob_high*100:.4f}% risk (ratio: {high_prob_high/high_prob_low:.1f}x)")
        
        print(f"\nKey Finding:")
        print(f"  Altitude affects risk by ~{(high_prob_high/high_prob_low - 1)*100:.0f}% (varies by density)")
        print(f"  Population density affects risk much more dramatically")
        print(f"  → Route planning should prioritize avoiding high-density areas")
        
        print("="*70 + "\n")


def analyze_density_to_casualty(altitude_stats, drone):
    """
    Main analysis function: generates full density-to-casualty model.
    """
    print("\n" + "="*70)
    print("DENSITY-TO-CASUALTY MODEL ANALYSIS")
    print("="*70)
    
    model = DensityToCasualtyModel(drone, altitude_stats)
    
    # Generate summary
    model.print_density_summary()
    
    # Export CSV
    model.export_density_casualty_csv('density_casualty_model.csv')
    
    # Generate plots
    model.generate_density_plots('density_casualty_plot.png')
    
    print("\n✓ Analysis complete!")
    print("\nGenerated files:")
    print("  - density_casualty_model.csv")
    print("  - density_casualty_plot.png")
    
    return model


if __name__ == '__main__':
    print("Density-to-Casualty Model Module")
    print("Use with altitude_analysis.py results")
