import requests
import datetime

import pandas as pd

from bokeh.models import Plot, graphs, ColumnDataSource, Range1d, Circle, HoverTool, BoxZoomTool, ResetTool, WheelZoomTool
from bokeh.io import show

import networkx as nx
from bokeh.io import output_file

# Output for the graph
output_file(fr"graphs/{datetime.date.today()}_infections.html")

# Hard coded mappings
country_mapping = {"FIN": "blue", "CHN": "red", "ITA": "green"}

# Get data from HS API
page = requests.get("https://w3qa5ydb4l.execute-api.eu-west-1.amazonaws.com/prod/finnishCoronaData")
df = pd.DataFrame(page.json()["confirmed"])
df["date"] = pd.to_datetime(df["date"])


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
plot = Plot(plot_width=500, plot_height=500,
            x_range=Range1d(-1.1, 1.1), y_range=Range1d(-1.1, 1.1))
plot.title.text = f"Corona cases Finland"

tools = [HoverTool(tooltips=[("id", "@id"), ("loc", "@location"), ("date", "@date"), ("origin", "@origin")]), WheelZoomTool(), ResetTool(), BoxZoomTool()]
plot.add_tools(*tools)

# Set Networkx graph to Bokeh
graph_renderer = graphs.from_networkx(G, **kwds_network)
graph_renderer.node_renderer.data_source.data = ColumnDataSource(data=plot_data).data

graph_renderer.node_renderer.glyph = Circle(size=10, fill_color="colors")

plot.renderers.append(graph_renderer)

# Show the plot
show(plot)
