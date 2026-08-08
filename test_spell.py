import services.spelling_service as sp


print("Loaded file:")
print(sp.__file__)


print("Class:")
print(sp.MyanmarSpellChecker)


checker = sp.MyanmarSpellChecker()


print("Object:")
print(checker.__dict__)