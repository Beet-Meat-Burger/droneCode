import numpy as np

def getRankedPopulationGrid(dataLoader, topN=50):
    """
    Ranks all 100m grid cells by population and returns GPS coordinates.
    :param topN: Number of top 'Hotspots' to return.
    """
    # 1. Read the population raster data
    popData = dataLoader.popRaster.read(1)
    transform = dataLoader.popRaster.transform
    
    # 2. Get indices of all pixels with population > 0
    # This creates a list of (row, col) where people live
    rows, cols = np.where(popData > 0.5) 
    
    # 3. Create a list of dictionaries with Value and Coordinates
    rankedPoints = []
    for r, c in zip(rows, cols):
        popCount = float(popData[r, c])
        
        # Calculate the CENTER of the 100m pixel for the coordinate
        # (c + 0.5, r + 0.5) moves the point from the Top-Left corner to the center
        lon, lat = transform * (c + 0.5, r + 0.5)
        
        rankedPoints.append({
            "population": int(popCount),
            "lat": lat,
            "lng": lon
        })

    # 4. Sort by population in descending order
    # Higher population = Higher Risk (Rank 1)
    rankedPoints.sort(key=lambda x: x['population'], reverse=True)

    return rankedPoints[:topN]

# --- Example Usage ---

