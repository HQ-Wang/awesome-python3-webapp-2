fields = ['id', 'name', 'password']
escaped_fields = list(map(lambda f: '`%s`' % f, fields))
a = ', '.join(escaped_fields)
print(a)
print(escaped_fields)