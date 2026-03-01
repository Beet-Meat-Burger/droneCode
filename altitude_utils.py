"""
Utility functions for loading and working with altitude analysis data.
"""

import csv
import json


def load_altitude_stats(csv_file='altitude_summary.csv'):
    """
    Loads altitude summary statistics from CSV.
    
    Args:
        csv_file: Path to altitude_summary.csv
        
    Returns:
        Dict: {altitude_ft: {metrics...}, ...}
    """
    stats = {}
    
    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                altitude_ft = int(float(row['altitude_ft']))
                
                stats[altitude_ft] = {
                    'altitude_ft': altitude_ft,
                    'avg_velocity_mps': float(row.get('avg_velocity_mps', 0)),
                    'avg_kinetic_energy': float(row.get('avg_kinetic_energy_j', 0)),
                    'avg_death_probability': float(row.get('avg_death_probability', 0)),
                    'casualty_probability': float(row.get('casualty_probability', 0)),
                    'num_simulations': int(row.get('num_simulations', 0)),
                }
    
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Cannot find {csv_file}. Run: python altitude_analysis.py"
        )
    
    return stats


def load_density_casualty_model(csv_file='density_casualty_model.csv'):
    """
    Loads density-to-casualty model data from CSV.
    
    Args:
        csv_file: Path to density_casualty_model.csv
        
    Returns:
        List: [{'altitude_ft': ..., 'population_density': ..., 'casualty_probability': ...}, ...]
    """
    data = []
    
    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append({
                    'altitude_ft': int(float(row['altitude_ft'])),
                    'population_density': float(row['population_density']),
                    'death_probability': float(row['death_probability']),
                    'probability_of_hit': float(row['probability_of_hit']),
                    'casualty_probability': float(row['casualty_probability']),
                    'casualty_probability_pct': float(row['casualty_probability_pct']),
                    'expected_casualties_per_1000': float(row['expected_casualties_per_1000'])
                })
    
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Cannot find {csv_file}. Run: python analyze_density_casualty.py"
        )
    
    return data


def get_density_threshold(casualty_probability_target, altitude_ft, model_data):
    """
    Finds maximum safe population density for given casualty probability target.
    
    Args:
        casualty_probability_target: Target casualty probability (e.g., 0.01 for 1%)
        altitude_ft: Flight altitude
        model_data: List from load_density_casualty_model()
        
    Returns:
        float: Maximum safe density (people/cell)
    """
    # Filter for this altitude
    alt_data = [d for d in model_data if d['altitude_ft'] == altitude_ft]
    
    if not alt_data:
        # Interpolate
        altitudes = sorted(set(d['altitude_ft'] for d in model_data))
        if altitude_ft < altitudes[0]:
            alt_data = [d for d in model_data if d['altitude_ft'] == altitudes[0]]
        elif altitude_ft > altitudes[-1]:
            alt_data = [d for d in model_data if d['altitude_ft'] == altitudes[-1]]
        else:
            # Linear interpolation
            idx = 0
            for i, alt in enumerate(altitudes):
                if alt <= altitude_ft:
                    idx = i
            alt1, alt2 = altitudes[idx], altitudes[idx+1]
            alt_data1 = [d for d in model_data if d['altitude_ft'] == alt1]
            alt_data2 = [d for d in model_data if d['altitude_ft'] == alt2]
            
            # For now, return from lower altitude (conservative)
            alt_data = alt_data1
    
    # Sort by density
    alt_data = sorted(alt_data, key=lambda x: x['population_density'])
    
    # Find max density where casualty_prob <= target
    for entry in alt_data:
        if entry['casualty_probability'] > casualty_probability_target:
            if entry == alt_data[0]:
                return 0
            return alt_data[alt_data.index(entry) - 1]['population_density']
    
    # All densities are safe
    return alt_data[-1]['population_density']


def print_density_safety_guide(model_data):
    """
    Prints a guide showing safe population densities for different targets.
    """
    print("\n" + "="*80)
    print("DENSITY SAFETY GUIDE")
    print("="*80)
    
    targets = [0.001, 0.01, 0.05, 0.1]  # 0.1%, 1%, 5%, 10%
    altitudes = sorted(set(d['altitude_ft'] for d in model_data))
    
    print(f"\nTarget Casualty Probability | Safe Density (people/cell) by Altitude\n")
    print(f"{'Target':<25}", end='')
    for alt in altitudes[::max(1, len(altitudes)//5)]:
        print(f"{alt:>10}ft", end='')
    print()
    print("-"*80)
    
    for target in targets:
        print(f"{target*100:>6.2f}% risk target      ", end='')
        for alt in altitudes[::max(1, len(altitudes)//5)]:
            threshold = get_density_threshold(target, alt, model_data)
            print(f"{threshold:>10.0f}  ", end='')
        print()
    
    print("="*80 + "\n")


if __name__ == '__main__':
    print("Utility module for altitude and density-casualty analysis")
    print("Import and use: from altitude_utils import load_altitude_stats")
