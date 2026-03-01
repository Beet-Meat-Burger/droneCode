"""
Test module for drone mission planning and compliance validation in Hong Kong.
"""
import numpy as np

from kimDroneGoon.geo import geodata
from kimDroneGoon.drone import Drone

# Hong Kong operational hubs
HK_HUBS = {
    "SCIENCE_PARK": {"lat": 22.4275, "lng": 114.2100, "name": "Science Park Sandbox"},
    "TOLO_HARBOUR": {"lat": 22.4350, "lng": 114.2250, "name": "Tolo Water Corridor"},
    "MA_ON_SHAN": {"lat": 22.4250, "lng": 114.2350, "name": "Ma On Shan Drop-off"},
    "TAI_PO_INDUSTRIAL": {"lat": 22.4600, "lng": 114.1850, "name": "Tai Po Hub"}
}


def evaluate_waypoint(drone, loader, target_lat, target_lng, target_alt):
    """
    Evaluates mission efficiency and compliance for a waypoint.
    
    Returns scoring breakdown and compliance status.
    """
    dist = drone.calculateHaversineDistance(target_lat, target_lng)
    benefit = ((drone.currentPayloadKg + 1.0) * dist) * 2
    risk_coeff = drone.calculateRiskCoefficient(loader)
    is_compliant, reason = drone.checkSandboxCompliance(loader)
    
    return {
        "distance_km": round(dist, 3),
        "benefit": round(benefit, 2),
        "risk_coeff": round(risk_coeff, 6),
        "compliant": is_compliant,
        "reason": reason
    }


def execute_mission(drone, loader, waypoints):
    """
    Executes a multi-waypoint mission with compliance checks and logging.
    """
    print(f"\n{'='*60}")
    print(f"MISSION: {drone.name} - {len(waypoints)} waypoints")
    print(f"{'='*60}")
    
    for i, pt in enumerate(waypoints):
        # Execute movement
        success = drone.flyToCoordinates(pt["lat"], pt["lng"], pt["alt"])
        
        if not success:
            print(f"\n❌ MISSION FAILED at WP {i}: Range exceeded or system error")
            break
        
        # Evaluate and log
        evaluation = evaluate_waypoint(drone, loader, pt["lat"], pt["lng"], pt["alt"])
        status = drone.getInfo()
        
        print(f"\nWaypoint {i}: {pt.get('label', 'Transit')}")
        print(f"  Position: ({status['telemetry']['location']['lat']:.4f}, "
              f"{status['telemetry']['location']['lng']:.4f}) @ {status['telemetry']['altitudeFt']}ft")
        print(f"  Classification: {status['identity']['hkCategoryCode']} - "
              f"{status['identity']['hkCategoryName']}")
        print(f"  Metrics: Distance={status['telemetry']['totalDistanceKm']:.2f}km | "
              f"Time={status['telemetry']['totalFlightTimeMin']:.1f}min")
        print(f"  Risk Coefficient: {evaluation['risk_coeff']:.6f}")
        print(f"  Compliance: {'✓ PASS' if evaluation['compliant'] else '✗ FAIL'} - {evaluation['reason']}")
        print(f"  {'-'*56}")


def generate_mission_waypoints(data_loader, hub_key, max_radius_km=5.0, min_pop=1000):
    """
    Generates mission waypoints from a hub to highest-population demand point.
    """
    if hub_key not in HK_HUBS:
        raise ValueError(f"Hub {hub_key} not found. Available: {list(HK_HUBS.keys())}")
    
    hub = HK_HUBS[hub_key]
    pop_data = data_loader.popRaster.read(1)
    transform = data_loader.popRaster.transform
    
    # Find demand points above threshold
    demands = []
    rows, cols = np.where(pop_data >= min_pop)
    
    for r, c in zip(rows, cols):
        lon, lat = transform * (c + 0.5, r + 0.5)
        dist = data_loader.popRaster._calculateDistance(hub["lat"], hub["lng"], lat, lon) \
               if hasattr(data_loader.popRaster, '_calculateDistance') \
               else Drone.calculateHaversineDistance(None, lat, lon)  # Fallback
        
        if dist <= max_radius_km:
            demands.append({"lat": lat, "lng": lon, "pop": int(pop_data[r, c])})
    
    if not demands:
        print(f"No demand points found within {max_radius_km}km of {hub['name']}")
        return []
    
    # Sort by population descending
    demands.sort(key=lambda x: x["pop"], reverse=True)
    target = demands[0]
    
    # Create 3-point mission profile
    return [
        {"lat": hub["lat"], "lng": hub["lng"], "alt": 100, "label": f"Takeoff @ {hub['name']}"},
        {"lat": (hub["lat"] + target["lat"]) / 2, "lng": (hub["lng"] + target["lng"]) / 2,
         "alt": 250, "label": "Transit Corridor"},
        {"lat": target["lat"], "lng": target["lng"], "alt": 150,
         "label": f"Delivery @ {target['pop']} people hotspot"}
    ]


# Example execution
if __name__ == "__main__":
    # Initialize drone
    my_drone = Drone(
        name="LogiWing_Alpha",
        emptyWeightKg=30.0,
        maxPayloadKg=20.0,
        maxRangeKm=40.0,
        maxSpeedKmh=60.0
    )
    
    # Load data
    data = geodata(
        "kimDroneGoon/datasets/worldpopHK/hkg_ppp_2020_UNadj_constrained.tif",
        "kimDroneGoon/datasets/LUMHK_RasterGrid_2024/BLU.tif",
        "kimDroneGoon/datasets/sandboxZones/map.geojson"
    )
    
    # Generate and execute mission
    waypoints = generate_mission_waypoints(data, "SCIENCE_PARK", my_drone.maxRangeKm)
    if waypoints:
        execute_mission(my_drone, data, waypoints)