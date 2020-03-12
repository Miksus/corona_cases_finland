import requests
import datetime

import pandas as pd
import numpy as np

from bokeh.plotting import figure
from bokeh.models import (
    Plot, graphs, ColumnDataSource, 
    Circle, Div,
    HoverTool, BoxZoomTool, ResetTool, WheelZoomTool, PanTool,
)

    
from bokeh.palettes import Spectral4
from bokeh.io import show

from bokeh.models.widgets import DataTable, DateFormatter, TableColumn

import networkx as nx
from bokeh.io import output_file
from bokeh.models import Jitter
from bokeh.layouts import gridplot

def jitter(G, df):
    jittering = nx.spring_layout(G)
    df["x"] = df.apply(lambda row: (row["x"] + jittering[row["id"]][0] * 5000), axis=1) #df["x"] +  np.random.normal(0, 2000,df.shape[0])
    df["y"] = df.apply(lambda row: (row["y"] + jittering[row["id"]][1] * 5000), axis=1) # df["y"] +  np.random.normal(0, 2000,df.shape[0])
    return df

def render_network_graph(fig, G, df, glyph_obj):
    #G_sub = G.subgraph(ids)
    #df_sub = df[df["id"].isin(ids)]
    
    positions = df.set_index("id")[["x", "y"]].apply(lambda row: {row.name: (row["x"], row["y"])}, axis=1).tolist()
    positions = {id_: pos for row in positions for id_, pos in row.items()}
    
    plot_data = {
        "index": list(G.nodes()), 
        "id": list(G.nodes()),
        "healthCareDistrict": df["healthCareDistrict"].tolist(),
        "date": df["date"].dt.date.tolist(),
        "origin": df["infectionSourceCountry"].tolist(),
        "case": df["case"].tolist(),
        "infection_from": df["infectionSource"].tolist(),
        "colors_case": df["case"].map({"recovered": "green", "deaths": "red", "confirmed":"orange"}).fillna("black").tolist(),
        "colors_origin": df["infectionSourceCountry"].map({"FIN": "blue", "CHN": "red", "ITA":"green"}).fillna("black").tolist()
    }
    datasource = ColumnDataSource(data=plot_data)
    graph_renderer = graphs.from_networkx(G, positions, legend="case")#, **kwds_network)
    graph_renderer.node_renderer.data_source.data = datasource.data

    graph_renderer.node_renderer.glyph = glyph_obj #Circle(size=10, fill_color="colors")
    
    fig.renderers.append(graph_renderer)
    return graph_renderer.node_renderer.data_source

def get_case(case, json):
    df = pd.DataFrame(page.json()[case])
    df["case"] = case
    return df


    
# Output for the graph
output_file(fr"graphs/{datetime.date.today()}_infections.html")

# Hard coded mappings
country_mapping = {"FIN": "blue", "CHN": "red", "ITA": "green"}

# Get data from HS API
page = requests.get("https://w3qa5ydb4l.execute-api.eu-west-1.amazonaws.com/prod/finnishCoronaData")

df = pd.DataFrame(page.json()["confirmed"])
df["infectionSourceCountry"] = df["infectionSourceCountry"].fillna("Unknown")
for case in ("confirmed", "recovered", "deaths"):
    cases = [str(person["id"]) for person in page.json()[case]]
    mask = df["id"].isin(cases)
    df.loc[mask, "case"] = case


df["date"] = pd.to_datetime(df["date"])

# Get supplementary
df_locs = pd.read_csv("sairaanhoitopiirit.csv", sep=";")
df["healthCareDistrictExpanded"] = df["healthCareDistrict"].replace(df_locs.set_index("Short name")["Full name"].to_dict())
df = df.join(df_locs.set_index("Full name")[["x", "y"]], on="healthCareDistrictExpanded")

# Network X stuff
kwds_network = dict(layout_function=nx.spring_layout)#, k=0.05,iterations=100)

G = nx.DiGraph()
G.add_nodes_from(df.id.tolist())

edge_list = df[df["infectionSource"].apply(lambda x: isinstance(x, int))].apply(lambda row: (row["id"], str(row["infectionSource"])), axis=1).tolist()

G.add_edges_from(
    edge_list
)

# Jittering
jittering = nx.spring_layout(G)
df["x"] = df.apply(lambda row: (row["x"] + jittering[row["id"]][0] * 5000), axis=1) #df["x"] +  np.random.normal(0, 2000,df.shape[0])
df["y"] = df.apply(lambda row: (row["y"] + jittering[row["id"]][1] * 5000), axis=1) # df["y"] +  np.random.normal(0, 2000,df.shape[0])




# Show with Bokeh

hoover = HoverTool(tooltips=[
    ("status", "@case"),
    ("id", "@id"), 
    ("infection from", "@infection_from"),
    ("location", "@healthCareDistrict"), 
    ("date", "@date{%F}"), 
    ("origin", "@origin"),
    
    ], formatters={'date': 'datetime'}
)
p = figure(plot_width=500, plot_height=750,
            x_range=(21021, 740463+((7818750-6570360)*0.1)), y_range=(6570360, 7818750),
            title="Corona Cases in Finland (Network Graph)",
          tools=[PanTool(), WheelZoomTool(), hoover, ResetTool(), BoxZoomTool()])

p.image_url(url=["../Taustakartta_8milj.png"],
            x=[21021], y=[6570360], w=[740463-21021], h=[7818750-6570360], 
            anchor="bottom_left")


today = pd.to_datetime(datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0), utc=df["date"].dt.tz)

# Maybe plot with different edges the most recent?
is_old = df["date"] < today
is_new = df["date"] >= today


new_infections = df[is_new]["id"].tolist()
old_infections = df[is_old]["id"].tolist()

#G_new = G.subgraph(new_infections)
#G_old = G.subgraph(old_infections)

# Set Networkx graph to Bokeh

glyph_obj = Circle(size=10, fill_color="colors_case") # , legend="case"
datasource = render_network_graph(p, G, df, glyph_obj=glyph_obj)

p.toolbar.active_scroll = p.select_one(WheelZoomTool)

p.xaxis.visible = False
p.xgrid.visible = False
p.ygrid.visible = False

columns = [
        TableColumn(field="id", title="id"), # , formatter=DateFormatter()
        TableColumn(field="infection_from", title="infection_from"),
    TableColumn(field="case", title="Status"),
    TableColumn(field="healthCareDistrict", title="healthCareDistrict"),
    TableColumn(field="date", title="date", formatter=DateFormatter()),
    TableColumn(field="origin", title="origin"),
    ]
data_table = DataTable(source=datasource, columns=columns, width=500, height=750)

div = Div(text="""
Color coding
<ul>
  <li style="color:green;">Recovered</li>
  <li style="color:orange;">Confirmed, active</li>
  <li style="color:red;">Dead</li>
</ul>
""",
width=500, height=100)


# Show the plot
layout = gridplot([[p, data_table], [div]])
show(layout)
