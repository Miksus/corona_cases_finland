import requests
import datetime

import pandas as pd
import numpy as np

from bokeh.plotting import figure
from bokeh.models import Plot, graphs, ColumnDataSource, Range1d, Circle, HoverTool, BoxZoomTool, ResetTool, WheelZoomTool, PanTool
from bokeh.io import show

import networkx as nx
from bokeh.io import output_file
from bokeh.models import Jitter

# Output for the graph
output_file(fr"graphs/{datetime.date.today()}_infections.html")

# Hard coded mappings
country_mapping = {"FIN": "blue", "CHN": "red", "ITA": "green"}

# Get data from HS API
page = requests.get("https://w3qa5ydb4l.execute-api.eu-west-1.amazonaws.com/prod/finnishCoronaData")
df = pd.DataFrame(page.json()["confirmed"])
df["date"] = pd.to_datetime(df["date"])

# Get supplementary
df_locs = pd.read_csv("sairaanhoitopiirit.csv", sep=";")
df["healthCareDistrictExpanded"] = df["healthCareDistrict"].replace(df_locs.set_index("Short name")["Full name"].to_dict())
df = df.join(df_locs.set_index("Full name")[["x", "y"]], on="healthCareDistrictExpanded")

# Jittering
df["x"] = df["x"] +  np.random.normal(0, 2000,df.shape[0])
df["y"] = df["y"] +  np.random.normal(0, 2000,df.shape[0])

# Position dict ({id: (x, y)})
positions = df.set_index("id")[["x", "y"]].apply(lambda row: {row.name: (row["x"], row["y"])}, axis=1).tolist()
positions = {id_: pos for row in positions for id_, pos in row.items()}

# Network X stuff
kwds_network = dict(layout_function=nx.spring_layout)#, k=0.05,iterations=100)

G = nx.DiGraph()
G.add_nodes_from(df.id.tolist())
G.add_edges_from(
    df[df["infectionSource"].apply(lambda x: isinstance(x, int))].apply(lambda row: (row["id"], str(row["infectionSource"])), axis=1).tolist()
    ,length=[200] * df[df["infectionSource"].apply(lambda x: isinstance(x, int))].shape[0]
)

plot_data = {"index": list(G.nodes()), 
             "id": list(G.nodes()),
             "location": df["healthCareDistrict"].tolist(),
             "date": df["date"].dt.date.astype(str).tolist(),
             "origin": df["infectionSourceCountry"].tolist(),
             "colors": df.infectionSourceCountry.map(country_mapping).fillna("k")}

# Show with Bokeh

p = figure(plot_width=500, plot_height=750,
            x_range=(21021, 740463+((7818750-6570360)*0.1)), y_range=(6570360, 7818750),
            title="Corona Cases in Finland (Network Graph)",
          tools=[PanTool(), WheelZoomTool(), HoverTool(tooltips=[("id", "@id"), ("location", "@location"), ("date", "@date"), ("origin", "@origin")]), ResetTool(), BoxZoomTool()])

p.image_url(url=["../Taustakartta_8milj.png"],
            x=[21021], y=[6570360], w=[740463-21021], h=[7818750-6570360], 
            anchor="bottom_left")


# Set Networkx graph to Bokeh
graph_renderer = graphs.from_networkx(G, positions)#, **kwds_network)
graph_renderer.node_renderer.data_source.data = ColumnDataSource(data=plot_data).data

graph_renderer.node_renderer.glyph = Circle(size=10, fill_color="colors")

p.renderers.append(graph_renderer)

# Show the plot
show(p)
