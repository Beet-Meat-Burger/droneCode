"""
Example: Risk Assessment Simulation for Drone Operations

Simulates potential failures at various altitudes and locations,
then estimates casualties and generates risk reports.
"""

from kimDroneGoon.geo import geodata
from kimDroneGoon.drone import Drone
from kimDroneGoon.simulation import DroneSimulator, RiskAssessment
from kimDroneGoon.visualize import visualizer

# Initialize data
data = geodata(
    "kimDroneGoon/datasets/worldpopHK/hkg_ppp_2020_UNadj_constrained.tif",
    "kimDroneGoon/datasets/LUMHK_RasterGrid_2024/BLU.tif",
    "kimDroneGoon/datasets/sandboxZones/map.geojson"
)

# Create drone
drone = Drone(
    name="DJI Matrice 300 RTK",
    emptyWeightKg=6.3,
    maxPayloadKg=2.7,
    maxRangeKm=15.0,
    maxSpeedKmh=82.8
)

# Initialize simulator with 1% failure probability
simulator = DroneSimulator(drone, data, failure_probability=3.2*10**-5)  # Adjusted for more realistic failure rates

print("\n>>> MULTI-SCENARIO RISK ASSESSMENT")
risk = RiskAssessment(simulator)

v = visualizer(data)

places = []
for i in range(1, 100):
    print(f"Finding random place on optimized path... Attempt {i}")
    places.append(v.getRandomPlaceOnDronePathPopNotZero(v.getOptimizedDronePath()))

# Run simulations for multiple random locations along the optimized path
for idx, (lat, lng) in enumerate(places):
    print(f"\n--- Simulation {idx+1} at Lat: {lat:.4f}, Lng: {lng:.4f} ---")
    for altitude_ft in range(50, 301, 50):  # Simulate failures at 50ft, 100ft, 150ft, 200ft, 250ft, and 300ft
        print(f"\nSimulating failure at {altitude_ft}ft...")
        risk.add_scenario(lat, lng, altitude_ft=altitude_ft, num_simulations=1000)

risk.summary_report()

print("\n✓ Simulation complete. Check console for detailed reports.")
