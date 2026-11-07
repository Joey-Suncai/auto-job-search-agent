# Spec: location-ranking text boxes (2026-11-05, a Greenhouse employer; Joey: every U.S. location is fine)

The candidate lives in Chicago and is open to every location in the United States. A free-text question that asks him to
RANK locations / offices and lists them in the question itself ("Please rank your location preference in order of most to
least preferred: Austin, Chicago, Greenwich, Houston, New York. If you are not open to a location, do not rank it.") →
every listed U.S. place, comma-separated, with Chicago first when it is listed, then the others in the order the question
lists them ("Chicago, Austin, Greenwich, Houston, New York"). Places outside the U.S. (marked "(CAN)", "Canada", "London,
UK" …) are left out. Places written "City, ST (USA)" separated by semicolons keep their full text ("Huntersville, NC (USA)").
When Chicago is not listed → all U.S. places in the listed order. A ranking question that does not list any places →
no answer (ask). A Yes/No question such as "Are you open to relocating?" is NOT a ranking question (never a list of places).
