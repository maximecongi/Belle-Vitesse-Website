from models.db import db


ROLE_TRANSLATION = {
    'super administrator': 'Super Administrateur',
    'super administrateur': 'Super Administrateur',
    'administrator': 'Administrateur',
    'administrateur': 'Administrateur',
    'manager': 'Manager',
    'commercial': 'Commercial',
    'user': 'Technicien',
    'technicien': 'Technicien',
}


class User(db.Model):
    """Modèle représentant un utilisateur du système (Administrateur, Manager, etc.)."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    mail = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(50))
    job = db.Column(db.String(100))
    role = db.Column(db.String(50))  # ex: Administrateur, Manager

    # Relations
    # Liste des check-outs effectués par cet utilisateur (contrôleur)
    controller_checkouts = db.relationship(
        "CheckoutVehicle", backref="controller", lazy=True)

    @property
    def role_lower(self):
        """Retourne le rôle en minuscules (par défaut 'technicien')."""
        if not self.role:
            return 'technicien'
        r = self.role.lower().strip()
        if r in ('super administrator', 'super administrateur'):
            return 'super administrateur'
        if r in ('administrator', 'administrateur'):
            return 'administrateur'
        if r in ('user', 'technicien'):
            return 'technicien'
        return r

    @property
    def role_display(self):
        """Retourne le libellé officiel français du rôle pour l'affichage."""
        return ROLE_TRANSLATION.get(self.role_lower, self.role or 'Technicien')

    @property
    def is_admin(self):
        """Retourne True si l'utilisateur est Administrateur ou Super Administrateur."""
        return self.role_lower in ('administrateur', 'super administrateur', 'administrator', 'super administrator')

    def is_mcp_capable(self):
        """Retourne True si l'utilisateur est autorisé à générer/utiliser des clés API MCP."""
        excluded_roles = ['technicien', 'user', 'guest', 'pilot']
        return self.is_admin and self.role_lower not in excluded_roles

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "mail": self.mail,
            "phone": self.phone,
            "job": self.job,
            "role": self.role_display,
        }

    def __repr__(self):
        return f"<User {self.firstname} {self.lastname}>"
