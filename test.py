import math

import numpy as np

from kimDroneGoon.rank import getRankedPopulationGrid
from kimDroneGoon.visualize import visualizer
from kimDroneGoon.geo import geodata
from kimDroneGoon.drone import Drone
# 1. setup the drone (category c logistics model)
my_drone = Drone(
    name="LogiWing_Alpha",
    emptyWeightKg=30.0,   # starts as category c
    maxPayloadKg=20.0,
    maxRangeKm=40.0,
    maxSpeedKmh=60.0
)

# 2. define mission waypoints (lat, lng, alt)
# route: science park -> tolo harbour (water) -> ma on shan (residential edge)
waypoints = [
    {"lat": 22.4275, "lng": 114.2100, "alt": 150}, # takeoff @ science park
    {"lat": 22.4350, "lng": 114.2250, "alt": 250}, # over tolo harbour
    {"lat": 22.4250, "lng": 114.2350, "alt": 200}, # approach ma on shan
]
def ratePath(drone, loader, targetLat, targetLng, targetAltFt):
    """
    Rates a flight path based on efficiency and safety.
    Pros: Cargo delivery, distance covered.
    Cons: Time taken, risk to people.
    """
    # 1. BENEFIT (Pros)
    # Value = (Cargo Weight + 1) * Distance. 
    # The '+1' ensures empty test flights still have a baseline distance benefit.
    dist = drone.calculateHaversineDistance(targetLat, targetLng)
    benefit = ((drone.currentPayloadKg + 1.0) * dist) * 2

    # 2. CONS (Costs)
    # Time is money: we penalize for the minutes spent in the air.
    timeCost = drone.calculateFlightTime(dist)
    
    # Population Risk: Using your riskCoefficient logic.
    # Higher riskCoefficient = Higher penalty.
    riskCoeff = drone.calculateRiskCoefficient(loader)
    riskPenalty = riskCoeff * 1

    # 3. FINAL CALCULATION
    totalScore = benefit - (timeCost + riskPenalty)

    # 4. COMPLIANCE CHECK (No penalty, just status)
    isCompliant, reason = drone.checkSandboxCompliance(loader)

    return {
        "score": round(totalScore, 2),
        "isCompliant": isCompliant,
        "complianceReason": reason,
        "breakdown": {
            "benefit": round(benefit, 2),
            "timeCost": round(timeCost, 2),
            "riskPenalty": round(riskPenalty, 6)
        }
    }

def runMissionScoring(drone, loader, waypoints):
    print(f"--- HK LAE MISSION LOG: {drone.name} ---")
    
    for i, pt in enumerate(waypoints):
        # Rate the leg based on benefits/cons
        rating = ratePath(drone, loader, pt["lat"], pt["lng"], pt["alt"])
        
        # Execute movement
        drone.flyToCoordinates(pt["lat"], pt["lng"], pt["alt"])
        status = drone.getInfo()
        
        print(f"WP {i} | Score: {rating['score']} | Legal: {rating['isCompliant']}")
        print(f"     | [+] Benefit: {rating['breakdown']['benefit']}")
        print(f"     | [-] Time Cost: {rating['breakdown']['timeCost']}")
        print(f"     | [-] Pop Risk: {rating['breakdown']['riskPenalty']}")
        
        if not rating['isCompliant']:
            print(f"     | ! REGULATORY ALERT: {rating['complianceReason']}")
        
        print("-" * 40)

def run_test_flight(drone, loader, path):
    print(f"--- Starting Test Flight: {drone.name} ---")
    
    for i, pt in enumerate(path):
        # 1. Execute Movement
        success = drone.flyToCoordinates(pt["lat"], pt["lng"], pt["alt"])
        
        if not success:
            print(f"Mission failed at waypoint {i}: Out of range or system error.")
            break
            
        # 2. Extract Status (using your exact keys)
        status = drone.getInfo()
        
        # 3. Check HK Compliance & Risk
        is_compliant, msg = drone.checkSandboxCompliance(loader)
        risk = drone.calculateRiskCoefficient(loader)
        
        # --- FIXED PRINTING LOGIC ---
        # Accessing: status["identity"]["class"] and status["telemetry"] sub-keys
        print(f"WP {i} | Class: {status['identity']['hkCategoryCode']} | Alt: {status['telemetry']['altitudeFt']}ft")
        print(f"     | Risk Coeff: {risk} | Compliant: {is_compliant} ({msg})")
        print(f"     | Dist: {status['telemetry']['totalDistanceKm']}km | Time: {status['telemetry']['totalFlightTimeMin']}min")
        print(f"     | Coords: {status['telemetry']['location']['lat']}, {status['telemetry']['location']['lng']}")
        print("-" * 30)
        
HK_HUBS = {
    "SCIENCE_PARK": {"lat": 22.4275, "lng": 114.2100, "name": "Science Park Sandbox"},
    "TOLO_HARBOUR": {"lat": 22.4350, "lng": 114.2250, "name": "Tolo Water Corridor"},
    "MA_ON_SHAN": {"lat": 22.4250, "lng": 114.2350, "name": "Ma On Shan Drop-off"},
    "TAI_PO_INDUSTRIAL": {"lat": 22.4600, "lng": 114.1850, "name": "Tai Po Hub"}
}

def calculateHaversineDistance(self, lat2, lng2):
        """Assumes Earth is a perfect sphere (Great Circle distance)."""
        R = self.config["earthRadiusKm"]
        lat1, lon1 = math.radians(self.currentLocation["lat"]), math.radians(self.currentLocation["lng"])
        lat2, lon2 = math.radians(lat2), math.radians(lng2)
        
        a = math.sin((lat2 - lat1) / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Example Execution:
# run_test_flight(my_drone, loader, waypoints)
def generateDemandWaypoints(dataLoader, startHubKey, maxRadiusKm=5.0, minPopDemand=1000):
    """
    Scans the grid for high-population 'demand' hotspots near a hub.
    :param minPopDemand: The threshold for a 'demand center' (people per 100m cell).
    """
    hub = HK_HUBS[startHubKey]
    popData = dataLoader.popRaster.read(1)
    transform = dataLoader.popRaster.transform
    
    # 1. Find all cells meeting the 'Demand' threshold within range
    demandPoints = []
    rows, cols = np.where(popData >= minPopDemand)
    
    for r, c in zip(rows, cols):
        lon, lat = transform * (c + 0.5, r + 0.5)
        # Use existing Haversine logic to filter by distance from Hub
        # (Assuming you have a helper or use the one inside Drone)
        dist = calculateHaversineDistance(hub["lat"], hub["lng"], lat, lon)
        
        if dist <= maxRadiusKm:
            demandPoints.append({"lat": lat, "lng": lon, "pop": int(popData[r, c])})
            
    # 2. Sort by highest demand first
    demandPoints.sort(key=lambda x: x["pop"], reverse=True)
    
    if not demandPoints:
        return []

    # 3. Create a mission to the top demand point
    target = demandPoints[0] # Pick the biggest 'customer'
    
    # Return a 3-point mission: [Takeoff, Mid-air Corridor, Drop-off]
    return [
        {"lat": hub["lat"], "lng": hub["lng"], "alt": 100, "label": "Hub Takeoff"},
        {"lat": (hub["lat"] + target["lat"])/2, "lng": (hub["lng"] + target["lng"])/2, "alt": 250, "label": "Transit"},
        {"lat": target["lat"], "lng": target["lng"], "alt": 150, "label": f"Demand Hotspot ({target['pop']} pax)"}
    ]

data = geodata(
    "kimDroneGoon\datasets\worldpopHK\hkg_ppp_2020_UNadj_constrained.tif",
    "kimDroneGoon\datasets\LUMHK_RasterGrid_2024\BLU.tif",
    "kimDroneGoon\datasets\sandboxZones\map.geojson"
)
# run it (assuming 'loader' is your HKDroneDataLoader instance)
runMissionScoring(my_drone, data, generateDemandWaypoints(data, "SCIENCE_PARK", my_drone.maxRangeKm))