from flask import Flask, render_template, request
import folium
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from Route_Optimization import predict_optimal_route

app = Flask(__name__)

def geocode_location(location):
    """Geocode an address to coordinates."""
    geolocator = Nominatim(user_agent="my_agent") 
    try:
        location = geolocator.geocode(location)
        if location:
            return location.latitude, location.longitude
        return None
    except (GeocoderTimedOut, GeocoderUnavailable):
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        city = request.form['city']
        start_point = request.form['start_point']
        destinations = request.form.getlist('destinations')

        # Remove empty addresses
        destinations = [dest for dest in destinations if dest.strip()]

        if not destinations:
            return render_template('index.html', error="Please enter at least one destination.")

        # Geocode the start point
        start_coords = geocode_location(start_point)
        if not start_coords:
            return render_template('index.html', error="Cannot find the starting address.")

        # Create a DataFrame for destinations
        destinations_data = []
        for dest in destinations:
            coords = geocode_location(dest)
            if coords:  # Only add if geocoding was successful
                destinations_data.append({
                    "City": city,
                    "Street Address": dest,
                    "Latitude": coords[0],
                    "Longitude": coords[1]
                })

        # Convert to DataFrame
        destinations_df = pd.DataFrame(destinations_data)

        if destinations_df.empty:
            return render_template('index.html', error="Cannot find any valid destination addresses.")

        # Predict the optimal route using Route_Optimization.py
        try:
            map_obj, total_distance, route_nodes = predict_optimal_route(city, start_coords, destinations_df)

            if map_obj is None or total_distance is None or route_nodes is None:
                return render_template('index.html', error="Unable to calculate the optimal route. Please try again with different addresses.")
            
            # Render the result template with the map and distance
            return render_template('result.html', map_html=map_obj._repr_html_(), distance=total_distance) 

        except Exception as e:
            app.logger.error(f"Error in predict_optimal_route: {str(e)}")
            return render_template('index.html', error="An error occurred while calculating the route. Please try again.")

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True) 