import sys
import folium
import geopandas as gpd
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl

class MapWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MapWindow, self).__init__(*args, **kwargs)
        self.setWindowTitle('Interactive World Map')
        self.setGeometry(100, 100, 800, 600)
        
        self.browser = QWebEngineView()
        self.setCentralWidget(self.browser)
        
        # Generate the map
        self.create_map()

    def create_map(self):
        try:
            # Load the GeoJSON file
            world = gpd.read_file('ne_110m_admin_0_countries.geojson')
            print("GeoJSON file loaded successfully.")
        except Exception as e:
            print(f"Failed to load GeoJSON file: {e}")
            return

        try:
            # Create a folium map
            m = folium.Map(location=[20, 0], zoom_start=2)
            
            # Add the GeoJSON layer to the map
            folium.GeoJson(world).add_to(m)
            
            # Save the map to an HTML file
            m.save('map.html')
            print("Map saved to map.html.")
        except Exception as e:
            print(f"Failed to create or save map: {e}")
            return

        try:
            # Load the HTML file into the web engine view
            self.browser.setUrl(QUrl.fromLocalFile('map.html'))
            print("Map loaded in QWebEngineView.")
        except Exception as e:
            print(f"Failed to load map in QWebEngineView: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MapWindow()
    window.show()
    sys.exit(app.exec_())

