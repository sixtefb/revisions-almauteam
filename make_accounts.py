"""Génère un mot de passe simple pour chaque membre et écrit accounts_PRIVE.txt (à ne pas commit)."""
import secrets, os
NAMES = ["Sixte", "Ulysse", "Alexandre", "Auguste", "Brune", "Victoria", "Jade", "Ginevra", "Capucine"]
WORDS = ["lac", "pin", "mer", "blé", "sol", "riz", "thé", "kiwi", "jade", "nuit", "fjord", "ciel", "brume", "olive", "cèdre", "menthe"]
def pwd():
    return f"{secrets.choice(WORDS)}-{secrets.choice(WORDS)}-{secrets.randbelow(90)+10}"
accounts = {n: pwd() for n in NAMES}
out = os.path.join(os.path.dirname(__file__), "..", "accounts_PRIVE.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write("Identifiants #AlmaUteam4ever (identifiant = prénom, sans tenir compte des majuscules)\n\n")
    for n, p in accounts.items():
        f.write(f"{n:10} {p}\n")
    f.write("\nÀ coller dans la variable d'environnement SEED_USERS (Render) :\n")
    f.write(",".join(f"{n}:{p}" for n, p in accounts.items()) + "\n")
print(open(out, encoding="utf-8").read())
