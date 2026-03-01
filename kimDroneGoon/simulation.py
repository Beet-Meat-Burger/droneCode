"""
Drone Failure Simulation Module

Simulates drone failures at given altitudes and estimates:
- Terminal velocity upon failure
- Impact location (drift from failure point)
- Casualty estimates based on population density
"""

import math
import random
import numpy as np
from shapely.geometry import Point
from kimDroneGoon.magic import MAGIC


class DroneSimulator:
    """
    Simulates drone failures and calculates impact statistics.
    
    Physics Model:
    - Terminal velocity depends on drag coefficient and drone mass
    - Horizontal drift during fall depends on wind and descent time
    - Casualty model: 
      * Probability of hitting person in impact zone (1m²)
      * Death probability based on kinetic energy/velocity
    """
    
    def __init__(self, drone, geo_loader, failure_probability=0.01):
        """
        Args:
            drone: Drone instance with flight specs
            geo_loader: GeometryData loader for population queries
            failure_probability: Probability drone fails [0, 1] (unused in current model)
        """
        self.drone = drone
        self.loader = geo_loader
        self.failure_prob = failure_probability
        self.physics = MAGIC
        
        # Aerodynamic constants
        self.AIR_DENSITY_KG_M3 = 1.225  # Sea level, standard atmosphere
        self.DRAG_COEFFICIENT = 0.47    # Approximate sphere/cylinder
        self.REFERENCE_AREA_M2 = 0.08   # Wing cross-section (~30cm diameter)
        
        # Impact constants
        self.IMPACT_AREA_M2 = 1.0       # ~1m² (drone footprint)
        self.LETHAL_KINETIC_ENERGY_J = 1000  # ~1000J threshold for blunt force fatality
        
    def calculate_terminal_velocity(self, altitude_ft, payload_kg=0.0):
        """
        Calculates TERMINAL velocity at given altitude (asymptotic limit).
        
        v_terminal = sqrt((2 * m * g) / (ρ * A * Cd))
        
        Note: Drone may not reach this velocity if altitude is too low.
        Use calculate_impact_velocity() for actual impact velocity.
        
        Args:
            altitude_ft: Flight altitude in feet
            payload_kg: Cargo weight
            
        Returns:
            Terminal velocity in m/s
        """
        # Total mass
        mass_kg = self.drone.emptyWeightKg + payload_kg
        
        # Gravitational acceleration
        g = 9.81
        
        # Air density decreases with altitude (simplified model)
        # ρ(h) = ρ₀ * exp(-h / 8500) for h in meters
        altitude_m = altitude_ft * self.physics["FT_TO_METERS"]
        air_density = self.AIR_DENSITY_KG_M3 * math.exp(-altitude_m / 8500)
        
        # Terminal velocity
        numerator = 2 * mass_kg * g
        denominator = air_density * self.REFERENCE_AREA_M2 * self.DRAG_COEFFICIENT
        
        v_terminal = math.sqrt(numerator / denominator)
        return v_terminal
        
    def calculate_impact_velocity(self, altitude_ft):
        """
        Calculates ACTUAL impact velocity accounting for acceleration and drag.
        
        The drone accelerates downward due to gravity, opposed by drag. 
        Velocity approaches terminal velocity exponentially.
        
        v(t) = v_terminal * (1 - exp(-t * g / v_terminal))
        
        However, we need the velocity after falling h meters, not after time t.
        Using energy + drag work is more practical:
        
        Work by gravity: W_g = m*g*h
        Work by drag: W_d = ∫F_drag ds (depends on velocity profile)
        
        For a first-order approximation, we use the fact that:
        - At low altitude: v ≈ sqrt(2*g*h) (free fall, negligible drag)
        - At high altitude: v ≈ v_terminal (drag dominates)
        
        We blend between these using a time constant approach.
        
        Args:
            altitude_ft: Failure altitude in feet
            
        Returns:
            Impact velocity in m/s
        """
        g = 9.81
        altitude_m = altitude_ft * self.physics["FT_TO_METERS"]
        
        # Calculate terminal velocity at this altitude
        v_terminal = self.calculate_terminal_velocity(altitude_ft)
        
        # Free-fall velocity (if no drag)
        v_free_fall = math.sqrt(2 * g * altitude_m)
        
        # Time constant for approaching terminal velocity
        # τ = m / (0.5 * ρ * A * Cd) = m / B
        mass_kg = self.drone.emptyWeightKg
        altitude_m_calc = altitude_ft * self.physics["FT_TO_METERS"]
        air_density = self.AIR_DENSITY_KG_M3 * math.exp(-altitude_m_calc / 8500)
        drag_coeff = 0.5 * air_density * self.REFERENCE_AREA_M2 * self.DRAG_COEFFICIENT
        tau = mass_kg / drag_coeff if drag_coeff > 0 else 1000  # Time constant (seconds)
        
        # Time to fall from this altitude (free fall approximation)
        # h = 0.5 * g * t^2 → t = sqrt(2h/g)
        t_fall_approx = math.sqrt(2 * altitude_m / g)
        
        # Velocity after falling h meters with drag:
        # v(h) = v_terminal * (1 - exp(-g * t_fall / v_terminal))
        # But t_fall = sqrt(2h/g) for free fall, actual t_fall with drag is longer
        # Conservative approach: use t ≈ sqrt(2h/g) which underestimates drag effect
        
        if v_terminal > 0:
            # How much of the way to terminal velocity do we get?
            exponent = min(5.0, g * t_fall_approx / v_terminal)  # Cap at 5.0 to avoid underflow
            velocity_factor = 1.0 - math.exp(-exponent)
            v_impact = v_terminal * velocity_factor
        else:
            v_impact = v_free_fall
        
        # Sanity check: velocity shouldn't exceed free fall or terminal velocity
        v_impact = max(0, min(v_impact, v_free_fall))  # Use free fall as upper bound (underestimates drag)
        
        return v_impact
    
    def calculate_descent_time(self, altitude_ft, terminal_velocity_ms):
        """
        Calculates time to fall from altitude to ground.
        
        Assumes constant terminal velocity after brief acceleration phase.
        
        Args:
            altitude_ft: Start altitude in feet
            terminal_velocity_ms: Terminal velocity in m/s
            
        Returns:
            Time to impact in seconds
        """
        altitude_m = altitude_ft * self.physics["FT_TO_METERS"]
        descent_time_sec = altitude_m / terminal_velocity_ms
        return descent_time_sec
    
    def calculate_impact_location(self, lat, lng, altitude_ft, wind_speed_ms=5.0):
        """
        Estimates impact location with random wind drift.
        
        Args:
            lat: Launch latitude
            lng: Launch longitude
            altitude_ft: Failure altitude
            wind_speed_ms: Avg wind speed during descent (m/s)
            
        Returns:
            Tuple (impact_lat, impact_lng)
        """
        # Calculate descent time using ACTUAL impact velocity
        v_impact = self.calculate_impact_velocity(altitude_ft)
        descent_time = self.calculate_descent_time(altitude_ft, v_impact)
        
        # Horizontal drift during descent
        drift_distance_m = wind_speed_ms * descent_time
        
        # Random wind direction (0-360 degrees)
        wind_direction = random.uniform(0, 360)
        wind_rad = math.radians(wind_direction)
        
        # Convert drift to lat/lng change
        # At equator: 1 degree ≈ 111 km
        lat_offset = (drift_distance_m / 111_000) * math.cos(wind_rad)
        lng_offset = (drift_distance_m / 111_000 / math.cos(math.radians(lat))) * math.sin(wind_rad)
        
        impact_lat = lat + lat_offset
        impact_lng = lng + lng_offset
        
        return impact_lat, impact_lng
    
    def estimate_casualties(self, impact_lat, impact_lng, altitude_ft):
        """
        Estimates casualties at impact location (binary outcome: 0 or 1).
        
        Model:
        - Impact area: 1m² (drone footprint)
        - Probability someone is in impact zone: based on population density
        - Death probability: based on actual impact velocity (kinetic energy), NOT altitude
        - Outcome: either 0 or 1 person killed (realistic for drone impact)
        
        Args:
            impact_lat: Impact latitude
            impact_lng: Impact longitude
            altitude_ft: Failure altitude (used to calculate terminal velocity)
            
        Returns:
            0 or 1 (binary: either no casualty or 1 casualty)
        """
        # Calculate ACTUAL impact velocity (accounting for drag & altitude)
        v_impact_mps = self.calculate_impact_velocity(altitude_ft)
        
        # Calculate kinetic energy at impact
        # E = 0.5 * m * v²
        drone_mass_kg = self.drone.emptyWeightKg
        kinetic_energy_j = 0.5 * drone_mass_kg * (v_impact_mps ** 2)
        
        # Death probability based on kinetic energy
        # Threshold: ~1000J for human fatality from blunt force trauma
        if kinetic_energy_j < 500:
            prob_death = 0.05  # Very low speed, minimal injury risk
        elif kinetic_energy_j < self.LETHAL_KINETIC_ENERGY_J:
            # Linear ramp from 5% to 50% between 500-1000J
            prob_death = 0.05 + (0.45 * (kinetic_energy_j - 500) / 500)
        else:
            # Linear ramp from 50% to 95% above 1000J
            prob_death = 0.50 + (0.45 * (kinetic_energy_j - 1000) / 5000)
            prob_death = min(0.95, prob_death)
        
        # Probability of hitting someone in 1m² impact zone
        try:
            pop_density = self.loader.getPopulationDensity(impact_lat, impact_lng)
        except:
            pop_density = 0.0
        
        # Population density is often people per cell (100m x 100m cell)
        # Convert to people per m²
        cell_area_m2 = self.physics["CELL_SIDE_METERS"] ** 2  # Typically 100x100 = 10,000 m²
        people_per_m2 = pop_density / cell_area_m2 if cell_area_m2 > 0 else 0.0
        
        # Expected people in 1m² impact zone
        expected_people = people_per_m2 * self.IMPACT_AREA_M2
        
        # Probability at least one person is in impact zone
        # For small λ: P(X ≥ 1) ≈ λ (Poisson approximation)
        prob_hit = min(1.0, expected_people)
        
        # Probability of casualty: must hit AND must die
        prob_casualty = prob_hit * prob_death
        
        # Stochastic outcome: binary (0 or 1)
        casualties = 1 if random.random() < prob_casualty else 0
        
        return casualties
    
    def run_simulation(self, lat, lng, altitude_ft, num_simulations=100000, debug=False):
        """
        Runs Monte Carlo simulation assuming drone has already failed at given altitude.
        
        Simulates num_simulations different failure outcomes based on random wind drift.
        
        Args:
            lat: Launch latitude
            lng: Launch longitude
            altitude_ft: Altitude at failure
            num_simulations: Number of simulation runs
            debug: Print detailed info for first few runs
            
        Returns:
            Dict with simulation statistics
        """
        impacts = []
        casualties_list = []
        terminal_velocities = []
        descent_times = []
        pop_densities = []
        
        for sim_idx in range(num_simulations):
            # Calculate physics - drone already failed, just calculate impact variations
            v_impact = self.calculate_impact_velocity(altitude_ft)
            terminal_velocities.append(v_impact)
            
            desc_time = self.calculate_descent_time(altitude_ft, v_impact)
            descent_times.append(desc_time)
            
            # Estimate impact location and casualties (varies due to random wind)
            impact_lat, impact_lng = self.calculate_impact_location(lat, lng, altitude_ft)
            impacts.append((impact_lat, impact_lng))
            
            # Get population at impact point
            pop_at_impact = self.loader.getPopulationDensity(impact_lat, impact_lng)
            pop_densities.append(pop_at_impact)
            
            casualties = self.estimate_casualties(impact_lat, impact_lng, altitude_ft)
            casualties_list.append(casualties)
            
            # Debug output for first few runs
            if debug and sim_idx < 3:
                print(f"  Run {sim_idx+1}: Impact at ({impact_lat:.4f}, {impact_lng:.4f}) → "
                      f"Pop={pop_at_impact:.0f} → Casualties={casualties:.1f}")
        
        # Aggregate statistics
        avg_lat = np.mean([p[0] for p in impacts])
        avg_lng = np.mean([p[1] for p in impacts])
        
        total_casualties = sum(casualties_list)
        
        stats = {
            "num_simulations": num_simulations,
            "altitude_ft": altitude_ft,
            "avg_terminal_velocity_ms": np.mean(terminal_velocities),
            "avg_descent_time_sec": np.mean(descent_times),
            "total_casualties": total_casualties,
            "max_casualties": max(casualties_list),
            "min_casualties": min(casualties_list),
            "avg_population_at_impact": np.mean(pop_densities),
            "impact_cluster_center": (avg_lat, avg_lng),
            "impact_points": impacts,
            "casualty_distribution": casualties_list,
            "population_distribution": pop_densities
        }
        
        return stats
    
    def print_simulation_report(self, stats):
        """Pretty-prints simulation results."""
        altitude_ft = stats['altitude_ft']
        v_term_mps = stats['avg_terminal_velocity_ms']
        
        # Calculate kinetic energy
        drone_mass_kg = self.drone.emptyWeightKg
        kinetic_energy_j = 0.5 * drone_mass_kg * (v_term_mps ** 2)
        
        # Calculate death probability
        if kinetic_energy_j < 500:
            prob_death = 0.05
        elif kinetic_energy_j < self.LETHAL_KINETIC_ENERGY_J:
            prob_death = 0.05 + (0.45 * (kinetic_energy_j - 500) / 500)
        else:
            prob_death = 0.50 + (0.45 * (kinetic_energy_j - 1000) / 5000)
            prob_death = min(0.95, prob_death)
        
        print("\n" + "="*60)
        print("DRONE FAILURE IMPACT SIMULATION")
        print("="*60)
        print(f"\nDrone Model: {self.drone.name}")
        print(f"Failure Altitude: {altitude_ft} ft")
        print(f"Simulations (with random wind): {stats['num_simulations']}")
        
        print(f"\nPhysics:")
        print(f"  Terminal Velocity: {v_term_mps:.2f} m/s")
        print(f"  Descent Time: {stats['avg_descent_time_sec']:.2f} seconds")
        print(f"  Kinetic Energy at Impact: {kinetic_energy_j:.1f} J")
        print(f"  Impact Area: 1 m² (drone footprint)")
        print(f"  Death Probability (if hit): {prob_death*100:.1f}%")
        
        print(f"\nPopulation Impact Analysis:")
        print(f"  Avg population density at impact: {stats['avg_population_at_impact']:.0f} people/cell")
        
        print(f"\nCasualty Estimates (Binary: 0 or 1 per impact):")
        print(f"  Total casualties across {stats['num_simulations']} simulations: {int(stats['total_casualties'])} people")
        print(f"  Casualty probability per impact: {stats['total_casualties'] / stats['num_simulations'] * 100:.2f}%")
        print(f"  Max in single simulation: {int(stats['max_casualties'])} people")
        
        if stats['impact_cluster_center']:
            avg_lat, avg_lng = stats['impact_cluster_center']
            print(f"\nAverage Impact Zone (considering wind drift):")
            print(f"  Lat: {avg_lat:.6f}, Lng: {avg_lng:.6f}")
        
        print("="*60 + "\n")


class RiskAssessment:
    """
    Aggregates risk metrics across multiple scenarios.
    """
    
    def __init__(self, simulator):
        self.simulator = simulator
        self.scenarios = []
    
    def add_scenario(self, lat, lng, altitude_ft, num_simulations=1000, debug=False):
        """Add a scenario to the risk assessment."""
        if debug:
            print(f"\n>>> Simulating {altitude_ft}ft failure at ({lat:.4f}, {lng:.4f})")
        stats = self.simulator.run_simulation(lat, lng, altitude_ft, num_simulations, debug=debug)
        self.scenarios.append({
            "location": (lat, lng),
            "altitude_ft": altitude_ft,
            "stats": stats
        })
        return stats
    
    def summary_report(self):
        """Generates risk summary across all altitude scenarios."""
        if not self.scenarios:
            print("No scenarios to assess.")
            return
        
        total_casualties = sum(s["stats"]["total_casualties"] for s in self.scenarios)
        max_single_event = max(s["stats"]["max_casualties"] for s in self.scenarios)
        worst_scenario = max(self.scenarios, key=lambda x: x["stats"]["max_casualties"])
        
        print("\n" + "="*60)
        print("MULTI-ALTITUDE RISK ASSESSMENT")
        print("="*60)
        print(f"Number of Altitude Scenarios: {len(self.scenarios)}")
        print(f"\nAltitudes Simulated:")
        for scenario in self.scenarios:
            alt = scenario["altitude_ft"]
            casualties = scenario["stats"]["total_casualties"]
            print(f"  {alt:4.0f} ft → {casualties:7d} total casualties across simulations")
        
        print(f"\nTotal Expected Casualties (all scenarios): {total_casualties:.0f}")
        print(f"Worst-Case Single Event: {max_single_event:.0f} at {worst_scenario['altitude_ft']} ft")
        print("="*60 + "\n")
