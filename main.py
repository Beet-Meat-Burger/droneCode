from kimDroneGoon.rank import getRankedPopulationGrid
from kimDroneGoon.visualize import visualizer
from kimDroneGoon.geo import geodata

data = geodata(
    "kimDroneGoon\datasets\worldpopHK\hkg_ppp_2020_UNadj_constrained.tif",
    "kimDroneGoon\datasets\LUMHK_RasterGrid_2024\BLU.tif",
    "kimDroneGoon\datasets\sandboxZones\map.geojson"
)
hotspots = getRankedPopulationGrid(data, topN=10)
for i, spot in enumerate(hotspots, 1):
    print(f"Rank {i}: {spot['population']} people at Lat: {spot['lat']:.4f}, Lng: {spot['lng']:.4f}")


#visual = visualizer(data)
#visual.addPopulationHeatmap()
#visual.addLandUseLayer()
#visual.addSandboxZones()
#visual.render()
