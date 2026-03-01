import math
from kimDroneGoon.magic import MAGIC

class Drone:
    def __init__(self, name, emptyWeightKg, maxPayloadKg, maxRangeKm, maxSpeedKmh, magic=MAGIC):
        self.physics = magic
        
        # Static Specs
        self.name = name
        self.emptyWeightKg = emptyWeightKg
        self.maxPayloadKg = maxPayloadKg
        self.maxRangeKm = maxRangeKm
        self.maxSpeedKmh = maxSpeedKmh
        
        # Internal State tracking
        self.currentPayloadKg = 0.0
        self.currentLocation = {"lat": 22.3193, "lng": 114.1694} 
        self.currentAltitudeFt = 0.0
        self.totalFlightTimeMinutes = 0.0
        self.totalDistanceTravelledKm = 0.0
        self.isOperational = True

    def getHkClassification(self):
        """
        HK CAD Regulatory Tiers (Cap. 448G + 2025 Category C Amendment).
        Hard-coded as the legal framework for the model.
        """
        mtom = self.emptyWeightKg + self.currentPayloadKg
        if mtom <= 0.25:
            return ("A1", "Standard (Micro)", "≤ 250g. No registration; max 100ft AGL.")
        elif mtom <= 7.0:
            return ("A2", "Standard (Small)", "250g-7kg. Registration required; max 300ft AGL.")
        elif mtom <= 25.0:
            return ("B", "Advanced", "7kg-25kg. Advanced Rating & CAD permit required.")
        elif mtom <= 150.0:
            return ("C", "Heavy SUA", "25kg-150kg. LAE Logistics class; strict oversight.")
        return ("AAM", "Unconventional", "> 150kg. Sandbox specific permits.")

    def calculateEffectiveSpeed(self):
        """ASSUMPTION: Linear speed degradation based on payload weight."""
        loadRatio = self.currentPayloadKg / self.maxPayloadKg if self.maxPayloadKg > 0 else 0
        penalty = self.physics["PAYLOAD_DRAG_COEFF"] * loadRatio
        return self.maxSpeedKmh * (1 - penalty)

    def calculateHaversineDistance(self, lat2, lng2):
        """ASSUMPTION: Earth is a perfect sphere for HK-scale distances."""
        R = self.physics["EARTH_RADIUS_KM"]
        lat1, lon1 = math.radians(self.currentLocation["lat"]), math.radians(self.currentLocation["lng"])
        lat2, lon2 = math.radians(lat2), math.radians(lng2)
        
        dlon, dlat = lon2 - lon1, lat2 - lat1
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def flyToCoordinates(self, lat, lng, altFt):
        """Updates state. Fails if range is exceeded."""
        if not self.isOperational:
            return False

        dist = self.calculateHaversineDistance(lat, lng)
        
        if (self.totalDistanceTravelledKm + dist) > self.maxRangeKm:
            self.isOperational = False # Battery/Fuel exhaustion
            return False

        # Time calculation based on physics assumptions
        flightTime = (dist / self.calculateEffectiveSpeed()) * 60
        
        self.totalDistanceTravelledKm += dist
        self.totalFlightTimeMinutes += flightTime
        self.currentLocation = {"lat": lat, "lng": lng}
        self.currentAltitudeFt = altFt
        return True

    def checkSandboxCompliance(self, dataLoader):
        """
        HK Compliance Logic:
        - Cat C must be in Sandbox.
        - Heights capped at 300ft (Sandbox) or 100ft (Standard/Urban).
        """
        catCode, _, _ = self.getHkClassification()
        inSandbox = dataLoader.isWithinSandbox(self.currentLocation["lat"], self.currentLocation["lng"])
        
        # HK CAD Altitude Limits
        maxAlt = 300 if inSandbox else 100
        if self.currentAltitudeFt > maxAlt:
            return False, f"Height violation: {self.currentAltitudeFt}ft > {maxAlt}ft"

        # LAE Restricted Class C
        if catCode == "C" and not inSandbox:
            return False, "Category C must remain in Sandbox zones."

        return True, "Compliant"

    def calculateRiskCoefficient(self, dataLoader):
        """
        ASSUMPTION: Impact Risk follows the 1:1 Lethal Radius Rule.
        Assumes people are uniformly distributed within the 100m grid cell.
        """
        pop = dataLoader.getPopulationDensity(self.currentLocation["lat"], self.currentLocation["lng"])
        
        # Density per m2
        cellArea = self.physics["CELL_SIDE_METERS"] ** 2
        rho = pop / cellArea 
        
        # Lethal Area (π * r^2) where r = altitude * multiplier
        altMeters = self.currentAltitudeFt * self.physics["FT_TO_METERS"]
        lethalRadius = altMeters * self.physics["LETHAL_RADIUS_MULT"]
        aExp = math.pi * (lethalRadius ** 2)
        
        return round(rho * aExp, 6)

    def updatePayload(self, weightKg):
        if weightKg > self.maxPayloadKg:
            raise ValueError("Exceeds Max Payload")
        self.currentPayloadKg = weightKg

    def getInfo(self):
        """
        Returns a detailed dictionary of drone specifications, 
        current telemetry, and HK regulatory status.
        """
        # Get all three parts from our HK classification logic
        catCode, catName, catDesc = self.getHkClassification()
        
        # Calculate current total mass for modeling
        mtom = self.emptyWeightKg + self.currentPayloadKg
        
        return {
            "identity": {
                "name": self.name,
                "hkCategoryCode": catCode,
                "hkCategoryName": catName,
                "hkDescription": catDesc
            },
            "specifications": {
                "emptyWeightKg": self.emptyWeightKg,
                "maxPayloadKg": self.maxPayloadKg,
                "currentPayloadKg": self.currentPayloadKg,
                "totalMassKg": mtom,
                "maxRangeKm": self.maxRangeKm,
                "maxSpeedKmh": self.maxSpeedKmh
            },
            "telemetry": {
                "location": {
                    "lat": round(self.currentLocation["lat"], 6),
                    "lng": round(self.currentLocation["lng"], 6)
                },
                "altitudeFt": self.currentAltitudeFt,
                "totalDistanceKm": round(self.totalDistanceTravelledKm, 3),
                "totalFlightTimeMin": round(self.totalFlightTimeMinutes, 2),
                "isOperational": self.isOperational
            }
        }
