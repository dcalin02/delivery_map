import streamlit as st
import openrouteservice as ors
import folium
import pandas as pd
import re
import math
import time  

st.set_page_config(layout="wide")

@st.cache_data(ttl=3600)  
def load_google_sheet_data(sheet_url):
    return pd.read_csv(sheet_url)

sheet_url = "https://docs.google.com/spreadsheets/d/1q8-nD8HJUps-mD1AVHDpB5klP-2yiivMSU1CXP5TKrU/export?format=csv&gid=1490221776"
sheet_url_2 = "https://docs.google.com/spreadsheets/d/1q8-nD8HJUps-mD1AVHDpB5klP-2yiivMSU1CXP5TKrU/export?format=csv&gid=1465567900"

log = load_google_sheet_data(sheet_url)
log['ID_PRODUS'] = log['ID_PRODUS'].astype(str).str.replace('.0',"")
mag = load_google_sheet_data(sheet_url_2)

order_type_mapping = {
    "STANDARD": [
        {"range": "STANDARD 0-15KM","pret":48, "min_km": 0, "max_km": 15, "cod":"11758670", "cod_desc":"12162290",'pret_desc':210,"cod_km":None,"pret_km":None},
        {"range": "STANDARD 15-20KM","pret":108, "min_km": 15, "max_km": 20, "cod":"11758684", "cod_desc":"12162290",'pret_desc':210,"cod_km":None,"pret_km":None},
        {"range": "STANDARD 20-30KM","pret":108, "min_km": 20, "max_km": 30, "cod":"11758691", "cod_desc":"12162290",'pret_desc':210,"cod_km":None,"pret_km":None},
        {"range": "STANDARD 30-50KM","pret":168, "min_km": 30, "max_km": 50, "cod":"11758705", "cod_desc":None,'pret_desc':None,"cod_km":None,"pret_km":None},
        {"range": "STANDARD >50KM","pret":168, "min_km": 50, "max_km": None, "cod":"11758705", "cod_desc":None,'pret_desc':None,"cod_km":"11859316","pret_km":2.5},
    ]
}


mag[['Latitude', 'Longitude']] = mag['lat_long'].str.split(",", expand=True)
mag = mag[['store_name', 'adress', 'Latitude', 'Longitude']]

st.title("Calculator tip de livrare")
st.markdown("<hr>", unsafe_allow_html=True)

client = ors.Client(key='5b3ce3597851110001cf6248571486db3ef0458ea19d9d4783b68797', requests_kwargs={'verify': False})

@st.cache_data(ttl=3600)
def geocode_address(address):
    geocode_result = client.pelias_search(address)
    coords = geocode_result['features'][0]['geometry']['coordinates']
    return coords

if 'product_entries' not in st.session_state:
    st.session_state['product_entries'] = [{'ID_PRODUS': '', 'quantity': 1}]  # Start with one product added by default

with st.sidebar:
    with st.container(border=True):
        store_names = mag['store_name'].unique()
        selected_store = st.selectbox("Selectați un magazin:", store_names, key="store_selection")
        
    store_info = mag[mag['store_name'] == selected_store].iloc[0]

    with st.container(border=True):
        start_lat = float(store_info['Latitude'])  # Use latitude from mag DataFrame
        start_lon = float(store_info['Longitude'])  # Use longitude from mag DataFrame
        start_address = store_info['adress']  # Display the address for reference
        
    with st.container(border=True):
        st.subheader("Adresa de destinație")
    
        end_col1, end_col2, end_col3, end_col4 = st.columns([2, 2, 2, 2])

        with end_col1:
            end_street = st.text_input("Strada", "", key="end_street", max_chars=100)
    
        with end_col2:
            end_city = st.text_input("Oraș", "", key="end_city", max_chars=50)
    
        with end_col3:
            end_country = st.text_input("Țară", "Romania", key="end_country", max_chars=50)

        with end_col4:
            end_postal_code = st.text_input("Cod poștal", "", key="end_postal_code", max_chars=10)

    # Add and remove products in the sidebar
    with st.container(border=True):
        st.subheader("Produse")
        if st.button("Adaugă produs"):
            st.session_state['product_entries'].append({'ID_PRODUS': '', 'quantity': 1})  # Adds a new product entry
  
        if st.button("Șterge toate produsele"):
            st.session_state['product_entries'] = []  # Clears all product entries
        

        # Display inputs for products and calculate weight for each product entry
        for i, entry in enumerate(st.session_state['product_entries']):
            st.write(f"**Produs {i + 1}:**")
            col1_inner, col2_inner = st.columns([3, 1])
            with col1_inner:
                ID_PRODUS = st.text_input(f"Introduceți ID-ul produsului {i+1}:", entry['ID_PRODUS'], key=f"ID_PRODUS_{i}")
                quantity_key = f"quantity_{i}"
                quantity = st.number_input(f"Introduceți cantitatea {i+1}:", min_value=1, step=1, 
                                       key=quantity_key, value=entry['quantity'], on_change=lambda: update_quantity(i))
        

            with col2_inner:
                remove_button = st.button(f"Șterge", key=f"delete_{i}")
                if remove_button:
                    st.session_state['product_entries'].remove(entry)
                    time.sleep(1)

            if ID_PRODUS:
                product_data = log[log["ID_PRODUS"] == ID_PRODUS]
                if not product_data.empty:
                    product_name = product_data["DENUMIRE_PRODUS"].values[0]
                    weight_per_unit = product_data["GREUTATE_NET_KG"].values[0]
                
                    st.write(f"**Produs selectat:** {product_name}")
                
                    entry['ID_PRODUS'] = ID_PRODUS
                    entry['quantity'] = quantity
                    weight_total = weight_per_unit * quantity

                    st.write(f"**Greutate produs {i+1}:** {weight_total:.2f} kg")
                    st.markdown("<hr>", unsafe_allow_html=True)

# Function to handle quantity update in session state
def update_quantity(index):
    st.session_state['product_entries'][index]['quantity'] = st.session_state[f"quantity_{index}"]

# The main section where calculations and results are displayed
with st.container():
    total_weight = 0
    total_distance_km = 0  # Initialize distance
    nr_livrari=1

    if start_lat and start_lon and end_street and end_city and end_country:
        full_end_address = f"{end_street}, {end_city}, {end_country}"
        if end_postal_code:
            full_end_address += f", {end_postal_code}"

        # Calculate total weight for all products
        for entry in st.session_state['product_entries']:
            ID_PRODUS = entry.get('ID_PRODUS', '')
            quantity = entry.get('quantity', 0)
            
            if ID_PRODUS:
                product_data = log[log["ID_PRODUS"] == ID_PRODUS].iloc[0]
                weight_per_unit = product_data["GREUTATE_NET_KG"]
                total_weight += weight_per_unit * quantity

        try:
            # Geocode only the destination address
            end_coords = geocode_address(full_end_address)

            # Get route information from OpenRouteService
            route = client.directions(coordinates=[[start_lon, start_lat], end_coords], profile='driving-car', format='geojson')
            total_distance_meters = route['features'][0]['properties']['segments'][0]['distance']
            total_distance_km = total_distance_meters / 1000  # Convert to kilometers
            
            if total_distance_km-50>0: 
                extra_km=2*(total_distance_km-50)
            else: extra_km=0

            nr_livrari=math.ceil(total_weight/1500)

            # Display total distance and weight
            st.write(f"**Distanța totală:** {math.ceil(total_distance_km)} km")
            st.write(f"**Kilometri suplimentari:** {math.ceil(extra_km)} km")
            st.write(f"**Greutate totală:** {total_weight:.2f} kg")
            st.write(f"**Numar de livrari:** {nr_livrari} livrari")
            
            st.markdown("<hr>", unsafe_allow_html=True)

            
            order_type = None
            order_code_desc= None
            order_code_km=None
            nr_desc=None
            nr_km=None
            denumire_desc=None
            denumire_km=None
            pret_desc=None
            pret_km=None
            pret_total_desc= None
            pret_total_km= None
            
            is_deployment = st.checkbox('Adauga serviciu de descarcare')
            if total_distance_km>30 and is_deployment:
                st.warning("Serviciul de descarcare nu poate fi adăugat pentru distanțe mai mari de 50 km.")

            for order in order_type_mapping["STANDARD"]:
                if order["min_km"] <= total_distance_km < (order["max_km"] if order["max_km"] is not None else float('inf')):
                    order_type = order["range"]
                    order_code=order['cod']
                    
                    if total_distance_km<=30 and is_deployment==True:
                        order_code_desc=order['cod_desc']
                        nr_desc=1*nr_livrari
                        denumire_desc="DESCARCARE 0-30KM"
                        pret_desc= order['pret_desc']
                        pret_total_desc=pret_desc*nr_desc
                        
                    else: 
                        order_code_desc=None  
                        nr_descs=None 
                        denumire_desc=None
                        pret_desc= None
                        pret_total_desc= None

                    if total_distance_km>50:
                        denumire_km="TARIF KM SUPLIMENTARI"
                        order_code_km=order['cod_km']
                        nr_km=math.ceil(extra_km*nr_livrari) 
                        pret_km=order['pret_km']
                        pret_total_km=pret_km*nr_km
                    break
            
            data = {"Tip livrare": [order_type,denumire_desc,denumire_km], 
                    "Cod livrare": [order_code,order_code_desc,order_code_km],
                    "Cantitate [buc]":[nr_livrari,nr_desc,nr_km],
                    "Cost serviciu [RON]":[order['pret'],pret_desc,pret_km],
                    "Cost total serviciu [RON":[order['pret']*nr_livrari,pret_total_desc,pret_total_km],}
            
                
            df=pd.DataFrame(data)
            df = df.dropna(how='all')
            st.dataframe(df,hide_index=True)
            
            if pret_total_desc is None: 
                pret_total_desc=0
            else: pret_total_desc=pret_total_desc

            if pret_total_km is None: 
                pret_total_km=0
            else: pret_total_km=pret_total_km
            
            
            st.write(f"**Cost total livrare:** {pret_total_desc+pret_total_km+order['pret']*nr_livrari} RON")
                
        except Exception as e:
            st.error(f"Error calculating the route: {e}")
    else:
        st.write("**Completează adresa de destinație pentru calcularea distanței.**")

    st.markdown("<hr>", unsafe_allow_html=True)

    # Show checkboxes for hiding/showing the map
    show_map = st.checkbox("Arată harta", value=False)

    if show_map and start_lat and start_lon and end_street and end_city and end_country and total_distance_km > 0:
        def calculate_zoom_level(total_distance_km):
            if total_distance_km < 10:
                return 15  # Zoom in close for small distances
            elif total_distance_km < 50:
                return 12  # Medium zoom
            elif total_distance_km < 200:
                return 9  # Less zoomed in for larger distances
            elif total_distance_km < 1000:
                return 6  # Even less zoom for very large distances
            else:
                return 4  # Zoomed out for really large distances (e.g., global scale)
        zoom_level = calculate_zoom_level(total_distance_km)
        with st.container(border=True):
            try:
                
                m = folium.Map(location=[start_lat, start_lon], zoom_start=zoom_level)
                
                # Add a marker for the starting location (store)
                folium.Marker(
                    location=[start_lat, start_lon],
                    popup=f"Magazin: {selected_store}",
                    icon=folium.Icon(color="green")
                ).add_to(m)
                
                # Add a marker for the destination
                folium.Marker(
                    location=[end_coords[1], end_coords[0]],
                    popup=f"Destinație: {full_end_address}",
                    icon=folium.Icon(color="red")
                ).add_to(m)
                
                # Draw the route
                folium.PolyLine(
                    locations=[list(reversed(coord)) for coord in route['features'][0]['geometry']['coordinates']],
                    color="blue"
                ).add_to(m)
                
                # Display the map
                map_html = m._repr_html_()
                st.components.v1.html(map_html, height=375, width=790)  # Larger map

            except Exception as e:
                st.error(f"Error displaying the map: {e}")

    # Add a checkbox to toggle visibility of the log database
    show_log = st.checkbox("Arată nomenclatorul de produse", value=False)
    
    if show_log:
        with st.container(border=True):
            st.write("**Nomenclator produse:**")
            log_styled = log.style.hide(axis="index")
            st.dataframe(log,hide_index=True)
