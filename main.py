import requests
import datetime

import pandas as pd
import numpy as np

from bokeh.plotting import figure
from bokeh.models import (
    Plot, graphs, ColumnDataSource, 
    Circle, Div,
    HoverTool, BoxZoomTool, ResetTool, WheelZoomTool, PanTool,
    Panel, Tabs, Span
)

    
from bokeh.palettes import Spectral4
from bokeh.io import show

from bokeh.models.widgets import DataTable, DateFormatter, TableColumn

import networkx as nx
from bokeh.io import output_file
from bokeh.models import Jitter
from bokeh.layouts import gridplot
from bokeh.transform import jitter
from bokeh.palettes import Category20

# Utils
def jitter_coordinates(df):
    G = nx.DiGraph()
    G.add_nodes_from(df.id.tolist())

    edge_list = df[df["infectionSource"].apply(lambda x: isinstance(x, int))].apply(lambda row: (row["id"], str(row["infectionSource"])), axis=1).tolist()

    G.add_edges_from(
        edge_list
    )
    jittering = nx.spring_layout(G)
    df["x"] = df.apply(lambda row: (row["x"] + jittering[row["id"]][0] * 5000), axis=1) #df["x"] +  np.random.normal(0, 2000,df.shape[0])
    df["y"] = df.apply(lambda row: (row["y"] + jittering[row["id"]][1] * 5000), axis=1) # df["y"] +  np.random.normal(0, 2000,df.shape[0])
    del G
    return df


def set_case_status(df, page_json):
    df["infectionSourceCountry"] = df["infectionSourceCountry"].fillna("Unknown")
    for case in ("confirmed", "recovered", "deaths"):
        cases = [str(person["id"]) for person in page_json[case]]
        mask = df["id"].isin(cases)
        df.loc[mask, "case"] = case
    return df

def set_coordinates(df):
    df_locs = pd.read_csv("sairaanhoitopiirit.csv", sep=";")
    df["healthCareDistrictExpanded"] = df["healthCareDistrict"].replace(df_locs.set_index("Short name")["Full name"].to_dict())
    df = df.join(df_locs.set_index("Full name")[["x", "y"]], on="healthCareDistrictExpanded")
    return df

def get_cases(json:dict):
    dfs = []
    for case in ("confirmed", "recovered", "deaths"):
        df = pd.DataFrame(json[case])
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df["id"] = df["id"].astype(str)
        dfs.append(df)
    return dfs


def get_data():
    """Get the data from the API 
    and add some supplementary information including:
        - location (x & y coordinates)
            - jittered a bit for not to be all on the same dot
        - current status of the confirmed invection
    """
    page = requests.get("https://w3qa5ydb4l.execute-api.eu-west-1.amazonaws.com/prod/finnishCoronaData")
    json = page.json()

    df_confirmed, df_recovered, df_died = get_cases(json)
    #df = pd.DataFrame(json["confirmed"])
    #df["date"] = pd.to_datetime(df["date"])

    df_confirmed = set_case_status(df_confirmed, json)
    df_confirmed = set_coordinates(df_confirmed)

    df_confirmed = jitter_coordinates(df_confirmed)

    return df_confirmed, df_recovered, df_died

def get_count_data(df, columns):
    """Turn the dataframe as cumulative count data per health care district
    
    Example output: (Some made up data)
    date       | HUS | Vaasa | ...
    2020-03-14 |  50 |   9   | ...
    2020-03-14 |  45 |   4   | ...
    """
    df_piv = df.copy()
    df_piv["date"] = df_piv["date"].dt.date
    df_piv = df_piv.pivot_table(columns=columns, values="id", index="date", aggfunc="count")

    df_piv = df_piv.reindex(pd.date_range(df_piv.index.min(), df_piv.index.max(), freq="D")).fillna(0).cumsum()
    df_piv.index = df_piv.index.date
    df_piv.index.name = "date"
    return df_piv

def get_active_cases(df, df_rec, df_dead, columns):
    df_count = get_count_data(df, columns=columns)
    if not df_rec.empty:
        df_rec = pd.merge(df_rec, df, how="left", left_on="id", right_on="id", suffixes=("", "_"))
        df_count = df_count.sub(get_count_data(df_rec, columns=columns) ,fill_value=0)
    if not df_dead.empty:
        df_dead = pd.merge(df_dead, df, how="left", left_on="id", right_on="id", suffixes=("", "_"))
        df_count = df_count.sub(get_count_data(df_dead, columns=columns) ,fill_value=0)
    return df_count

def get_datasource(df):
    "Get the Bokeh datasource used by most of the plots"
    plot_data = {
        "index": df["id"].tolist(), 
        "id": df["id"].tolist(),
        "healthCareDistrict": df["healthCareDistrict"].tolist(),
        "date": df["date"].dt.date.tolist(),
        "origin": df["infectionSourceCountry"].tolist(),
        "case": df["case"].tolist(),
        "infection_from": df["infectionSource"].tolist(),
        "colors_case": df["case"].map({"recovered": "green", "deaths": "red", "confirmed":"orange"}).fillna("black").tolist(),
        "colors_origin": df["infectionSourceCountry"].map({"FIN": "blue", "CHN": "red", "ITA":"green"}).fillna("black").tolist()
    }
    return ColumnDataSource(data=plot_data)

def render_network_graph(fig, datasource, df, glyph_obj):
    "Utility for plotting the network graph"
    #G_sub = G.subgraph(ids)
    #df_sub = df[df["id"].isin(ids)]
    G = nx.DiGraph()
    G.add_nodes_from(df.id.tolist())

    edge_list = df[df["infectionSource"].apply(lambda x: isinstance(x, int))].apply(lambda row: (row["id"], str(row["infectionSource"])), axis=1).tolist()

    G.add_edges_from(
        edge_list
    )
    positions = df.set_index("id")[["x", "y"]].apply(lambda row: {row.name: (row["x"], row["y"])}, axis=1).tolist()
    positions = {id_: pos for row in positions for id_, pos in row.items()}
    
    graph_renderer = graphs.from_networkx(G, positions, legend="case")#, **kwds_network)
    graph_renderer.node_renderer.data_source.data = datasource.data

    graph_renderer.node_renderer.glyph = glyph_obj #Circle(size=10, fill_color="colors")
    
    fig.renderers.append(graph_renderer)
    
    return graph_renderer.node_renderer.data_source


# Plots

def get_network_plot(datasource, df, toolbox):
    """Plot the network graph on a map of Finland

    Each dot represents a confirmed case and lines
    between them a contagion
    """
    p = figure(plot_width=500, plot_height=750,
                x_range=(21021, 740463+((7818750-6570360)*0.1)), y_range=(6570360, 7818750),
                title="Corona Cases in Finland (Network Graph)",
              tools=toolbox)

    p.image_url(url=["Taustakartta_8milj.png"],
                x=[21021], y=[6570360], w=[740463-21021], h=[7818750-6570360], 
                anchor="bottom_left")

    # Set Networkx graph to Bokeh

    glyph_obj = Circle(size=10, fill_color="colors_case") # , legend="case"
    render_network_graph(p, datasource, df, glyph_obj=glyph_obj)

    p.toolbar.active_scroll = p.select_one(WheelZoomTool)

    p.xaxis.visible = False
    p.xgrid.visible = False
    p.ygrid.visible = False

    div = Div(text="""
    Color coding
    <ul>
      <li style="color:green;">Recovered</li>
      <li style="color:orange;">Confirmed, active</li>
      <li style="color:red;">Dead</li>
    </ul>
    """,
    width=500, height=250)
    grid = gridplot([[p], [div]], toolbar_location=None)
    return grid

def get_datatable(datasource):
    "Get the Bokeh table of the data"
    columns = [
        TableColumn(field="id", title="id"), # , formatter=DateFormatter()
        TableColumn(field="infection_from", title="infection_from"),
        TableColumn(field="case", title="Status"),
        TableColumn(field="healthCareDistrict", title="healthCareDistrict"),
        TableColumn(field="date", title="date", formatter=DateFormatter()),
        TableColumn(field="origin", title="origin"),
    ]
    dt = DataTable(source=datasource, columns=columns, width=500, height=750)
    
    return dt

def get_timeline_plot(source, toolbox, names, y, title):
    "Plot the observations through time accross given y"
    p = figure(plot_width=1000, plot_height=300, y_range=names, x_axis_type='datetime',
               title=title, tools=toolbox)

    p.circle(x='date', y=jitter(y, width=0.6, range=p.y_range),  source=source, alpha=0.3, line_color="colors_case", fill_color="colors_case")

    p.toolbar.active_scroll = p.select_one(WheelZoomTool)
    return p
    

def get_timeseries_plot(df, toolbox, x_axis, names, title):
    "Plot an area plot of the total infections per health care district"
    p = figure(plot_width=1000, plot_height=500, title=title,
               tools=toolbox, x_axis_type='datetime',
                y_range=(0, df.iloc[-1].sum()), x_range=x_axis)#, x_range=(df_.index.min(), df_.index.max()))

    p.varea_stack(stackers=names, x='date', legend_label=names, 
                  source=df, color=Category20[len(names)]) # , color=brewer['Spectral'][11]
    
    p.toolbar.active_scroll = p.select_one(WheelZoomTool)
    p.legend.location = 'top_left'

    # Vertical line
    vline = Span(location=datetime.date.today(), dimension='height', line_color='blue', line_width=1)
    # Horizontal line
    hline = Span(location=0, dimension='width', line_color='black', line_width=1)

    p.renderers.extend([vline, hline])
    return p

if __name__ == "__main__":

    #output_file(fr"graphs/{datetime.date.today()}_infections.html")
    output_file(fr"status.html")

    df, df_rec, df_dead = get_data()

    df_count_loc = get_active_cases(df, df_rec, df_dead, columns=["healthCareDistrict"]) 
    df_count_orig = get_active_cases(df, df_rec, df_dead, columns=["infectionSourceCountry"]) 


    most_infected_loc = df_count_loc.iloc[-1].sort_values().index.tolist()
    most_infected_orig = df_count_orig.iloc[-1].sort_values().index.tolist()

    hoover = HoverTool(tooltips=[
        ("status", "@case"),
        ("id", "@id"), 
        ("infection from", "@infection_from"),
        ("location", "@healthCareDistrict"), 
        ("date", "@date{%F}"), 
        ("origin", "@origin"),

        ], formatters={'date': 'datetime'}
    )
    toolbox = [PanTool(), WheelZoomTool(), hoover, ResetTool(), BoxZoomTool()]
    datasource = get_datasource(df)

    p_net = get_network_plot(datasource, df, toolbox)
    data_table = get_datatable(datasource)

    p_obs = get_timeline_plot(datasource, toolbox, names=most_infected_loc, y="healthCareDistrict", title="Observations per location")
    p_area = get_timeseries_plot(df_count_loc, toolbox, p_obs.x_range, names=most_infected_loc, title="Active cases per location")

    p_obs_source = get_timeline_plot(datasource, toolbox, names=most_infected_orig, y="origin", title="Observations per origin")
    p_area_source = get_timeseries_plot(df_count_orig, toolbox, p_obs_source.x_range, names=most_infected_orig, title="Active cases per origin")

    tabs = Tabs(tabs=[
        Panel(child=gridplot([[p_net, data_table]]), title="Network"), 
        Panel(child=gridplot([[p_obs], [p_area]]), title="Location"),
        Panel(child=gridplot([[p_obs_source], [p_area_source]]), title="Origin") 
    ])

    div = Div(text=f"""
    <h2>Corona Dashboard for cases in Finland.</h2>
    Author: Mikael Koli
    <br>Updated: {datetime.datetime.now().strftime('%H:%M %d.%m.%Y')}
    """,
    width=500, height=100)

    show(gridplot([[div], [tabs]], toolbar_location=None))