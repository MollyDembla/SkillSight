"""Assign an explicit SkillSight custom role to a Firebase Auth user UID."""
import argparse
import os
import firebase_admin
from firebase_admin import auth

def main():
    project=os.getenv("FIREBASE_PROJECT_ID")
    if not project:
        raise SystemExit("Set FIREBASE_PROJECT_ID before assigning roles.")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("uid",help="Firebase Auth user UID")
    parser.add_argument("role",choices=["viewer","planner","admin"])
    args=parser.parse_args()
    try: app=firebase_admin.get_app()
    except ValueError: app=firebase_admin.initialize_app(options={"projectId":project})
    user=auth.get_user(args.uid,app=app)
    claims=dict(user.custom_claims or {})
    claims["role"]=args.role
    auth.set_custom_user_claims(args.uid,claims,app=app)
    print(f"Set role={args.role} for UID {args.uid}. The user must refresh their ID token (sign out and back in).")

if __name__=="__main__": main()
