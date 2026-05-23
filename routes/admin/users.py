from flask import flash, redirect, render_template, request, session, url_for

from services.admin.users import (
    create_user,
    delete_user,
    get_user,
    list_users,
    update_user,
)
from utils.decorators import require_roles

# Hiérarchie des rôles (plus le nombre est élevé, plus le rôle est privilégié)
ROLE_HIERARCHY = {
    'user': 1,
    'commercial': 2,
    'manager': 3,
    'administrator': 4,
    'super administrator': 5,
}

# Rôles assignables par chaque rôle (rôle-1 et en dessous)
ASSIGNABLE_ROLES = {
    'super administrator': ['Administrator', 'Manager', 'Commercial', 'User'],
    'administrator': ['Manager', 'Commercial', 'User'],
    'manager': [],
    'commercial': [],
    'user': [],
}


def _get_current_role_level():
    """Retourne le niveau hiérarchique du rôle de l'utilisateur connecté."""
    role = session.get("admin_user_role", "User").lower()
    return ROLE_HIERARCHY.get(role, 0)


def _get_assignable_roles():
    """Retourne la liste des rôles que l'utilisateur connecté peut attribuer."""
    role = session.get("admin_user_role", "User").lower()
    return ASSIGNABLE_ROLES.get(role, [])


def _get_target_role_level(user):
    """Retourne le niveau hiérarchique du rôle d'un utilisateur cible."""
    role = (user.role or "User").lower()
    return ROLE_HIERARCHY.get(role, 0)


def _is_self(target_user):
    """Vérifie si l'utilisateur cible est l'utilisateur connecté."""
    return target_user.id == session.get("admin_user_id")


def _can_manage_user(target_user):
    """Vérifie si l'utilisateur connecté peut modifier/supprimer un utilisateur cible.
    On peut gérer soi-même ou les utilisateurs de niveau strictement inférieur."""
    return _is_self(target_user) or _get_current_role_level() > _get_target_role_level(target_user)


def init_users_routes(app):

    @app.route("/admin/users")
    @require_roles('administrator')
    def admin_users_list():
        users = list_users()
        current_level = _get_current_role_level()
        return render_template(
            "admin/users_list.html",
            users=users,
            current_level=current_level,
            role_hierarchy=ROLE_HIERARCHY,
        )

    @app.route("/admin/users/new", methods=["GET", "POST"])
    @require_roles('administrator')
    def admin_user_create():
        assignable = _get_assignable_roles()

        if request.method == "POST":
            role = request.form.get("role", "User")

            # Validation : le rôle demandé doit être dans la liste autorisée
            if role not in assignable:
                flash("Vous n'avez pas les permissions pour attribuer ce rôle.", "error")
                return render_template("admin/user_form.html", is_edit=False, data=None, assignable_roles=assignable)

            data = {
                "firstname": request.form.get("firstname"),
                "lastname": request.form.get("lastname"),
                "mail": request.form.get("mail"),
                "role": role,
                "phone": request.form.get("phone"),
                "job": request.form.get("job")
            }
            if create_user(data):
                flash("Utilisateur créé avec succès.", "success")
                return redirect(url_for("admin_users_list"))
            flash("Erreur lors de la création de l'utilisateur.", "error")

        return render_template("admin/user_form.html", is_edit=False, data=None, assignable_roles=assignable)

    @app.route("/admin/users/<record_id>/edit", methods=["GET", "POST"])
    @require_roles('administrator')
    def admin_user_edit(record_id):
        user = get_user(record_id)
        if not user:
            flash("Utilisateur introuvable.", "error")
            return redirect(url_for("admin_users_list"))

        # Vérifier que l'utilisateur connecté peut gérer cet utilisateur
        if not _can_manage_user(user):
            flash("Vous ne pouvez pas modifier un utilisateur de rang égal ou supérieur.", "error")
            return redirect(url_for("admin_users_list"))

        assignable = _get_assignable_roles()

        editing_self = _is_self(user)

        if request.method == "POST":
            # Si l'utilisateur modifie son propre profil, le rôle reste inchangé
            if editing_self:
                role = user.role
            else:
                role = request.form.get("role", user.role)

                # Validation : le rôle demandé doit être dans la liste autorisée
                if role not in assignable:
                    flash("Vous n'avez pas les permissions pour attribuer ce rôle.", "error")
                    return render_template("admin/user_form.html", is_edit=True, data=user, record_id=record_id, assignable_roles=assignable, editing_self=editing_self)

            data = {
                "firstname": request.form.get("firstname"),
                "lastname": request.form.get("lastname"),
                "mail": request.form.get("mail"),
                "role": role,
                "phone": request.form.get("phone"),
                "job": request.form.get("job")
            }
            if update_user(record_id, data):
                flash("Utilisateur mis à jour avec succès.", "success")
                return redirect(url_for("admin_users_list"))
            flash("Erreur lors de la mise à jour de l'utilisateur.", "error")

        return render_template("admin/user_form.html", is_edit=True, data=user, record_id=record_id, assignable_roles=assignable, editing_self=editing_self)

    @app.route("/admin/users/<record_id>/delete", methods=["POST"])
    @require_roles('administrator')
    def admin_user_delete(record_id):
        user = get_user(record_id)
        if not user:
            flash("Utilisateur introuvable.", "error")
            return redirect(url_for("admin_users_list"))

        # Interdire la suppression de son propre compte et des utilisateurs de rang >= 
        if _is_self(user):
            flash("Vous ne pouvez pas supprimer votre propre compte.", "error")
            return redirect(url_for("admin_users_list"))

        if _get_current_role_level() <= _get_target_role_level(user):
            flash("Vous ne pouvez pas supprimer un utilisateur de rang égal ou supérieur.", "error")
            return redirect(url_for("admin_users_list"))

        if delete_user(record_id):
            flash("Utilisateur supprimé avec succès.", "success")
        else:
            flash("Erreur lors de la suppression de l'utilisateur.", "error")
        return redirect(url_for("admin_users_list"))
