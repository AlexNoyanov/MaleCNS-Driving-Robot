from neuprint import Client, fetch_neurons, fetch_adjacencies
import navis
import navis.interfaces.neuprint as neu

# get token from neuprint.janelia.org after creating an account
client = Client("https://neuprint.janelia.org", dataset='male-cns:v1.0', token="YOUR_TOKEN")

# pull neuron metadata + connectivity for a cell type
neurons, syndist = fetch_neurons("DNge104")
outgoing, info = fetch_adjacencies("DNge104")

# pull actual 3D skeletons and plot them
skels = neu.fetch_skeletons(neu.NeuronCriteria(type="DNge104"))
fig, ax = navis.plot2d(skels, view=('z', 'x'), radius=True)
