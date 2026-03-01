"""
Analyze Density-to-Casualty Relationship

Generates complete population density → casualty probability model.
Shows how density impacts risk at different altitudes.

Usage:
    python analyze_density_casualty.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kimDroneGoon.drone import Drone
from altitude_utils import load_altitude_stats, print_density_safety_guide, load_density_casualty_model
from density_casualty_model import analyze_density_to_casualty


def main():
    print("\n" + "#"*70)
    print("# POPULATION DENSITY → CASUALTY PROBABILITY ANALYSIS")
    print("#"*70)
    
    # Load drone specs
    print("\n[*] Loading drone specifications...")
    drone = Drone()
    print(f"    Mass: {drone.mass}g")
    print(f"    Specs loaded ✓")
    
    # Load altitude analysis results
    print("\n[*] Loading altitude analysis results...")
    try:
        altitude_stats = load_altitude_stats('altitude_summary.csv')
        print(f"    Loaded stats for {len(altitude_stats)} altitudes")
        print(f"    Altitude range: {min(altitude_stats.keys())}ft - {max(altitude_stats.keys())}ft")
    except FileNotFoundError:
        print("\n    ERROR: altitude_summary.csv not found!")
        print("    First run: python altitude_analysis.py")
        return
    
    # Run analysis
    model = analyze_density_to_casualty(altitude_stats, drone)
    
    # Load generated model for safety guide
    print("\n[*] Loading generated model for safety guide...")
    try:
        model_data = load_density_casualty_model('density_casualty_model.csv')
        print_density_safety_guide(model_data)
    except FileNotFoundError:
        print("    (Safety guide skipped - CSV not ready yet)")
    
    print("\n[✓] Density-to-Casualty Model Generated Successfully!")
    print("\nNext Steps:")
    print("  1. Review density_casualty_model.csv for density thresholds")
    print("  2. Check density_casualty_plot.png for visualization")
    print("  3. Use this for route planning: avoid high-density areas")
    print("  4. Integrate into routing optimization")


if __name__ == '__main__':
    main()
