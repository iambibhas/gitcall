from app import db, User, UserRepo
db.drop_all()
db.create_all()

user = User('iambibhas', 'asd@asd.com', 'asdasdasd')
db.session.add(user)
db.session.commit()
print user

userrepo = UserRepo(user.id, 123123, 'asdasd')
db.session.add(userrepo)
db.session.commit()
print userrepo

print user.linked_repos
print userrepo.user