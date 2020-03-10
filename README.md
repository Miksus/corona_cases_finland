# Corona Infections Finland (Network Graph)
![Example](example.png)

Picture Updated: 10.3.2020

This is a simple network graph to inspect how the Corona infections spread from person to person in Finland.
This graph uses HS's Corona open data API (https://github.com/HS-Datadesk/koronavirus-avoindata).
Requires Python 3 with packages: Networkx (tested with 2.4), Pandas (tested with 1.0.0) & Bokeh (tested with 1.4.0).

Definition:
- Each dot represents an infection case
- Each link represents a known infection (from person to person)
- Colors represents the source country. Hard coded mapping (black represents lack of mapping).
  - Blue: Finland
  - Green: Italy
  - Red: China
  - Black: Unspecified

The background map is from Maanmittauslaitos (https://www.maanmittauslaitos.fi/avoindata-lisenssi-cc40).

Author: Mikael Koli
