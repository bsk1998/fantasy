# Fichier complet : backend/app/scraper.py
def recuperer_effectif_web(team_name):
    """
    Simule la recherche sur le web.
    Si l'équipe est dans ce dictionnaire, elle est 'open'. 
    Sinon, elle reste 'locked'.
    """
    # Ici, tes données réelles (pas de saisie manuelle dans le code principal)
    data_source = {
        "France": [
            {"id": 1, "name": "K. Mbappé", "position": "A", "price": 18.5},
            {"id": 2, "name": "A. Griezmann", "position": "M", "price": 12.0},
            {"id": 3, "name": "W. Saliba", "position": "D", "price": 9.5},
            {"id": 4, "name": "M. Maignan", "position": "G", "price": 8.0}
        ],
        "Argentine": [
            {"id": 5, "name": "L. Messi", "position": "A", "price": 16.0},
            {"id": 6, "name": "E. Martinez", "position": "G", "price": 9.0}
        ]
    }
    return data_source.get(team_name)