from django.core.signing import Signer
from django.http import HttpResponse
from django.shortcuts import redirect

signer = Signer()


class URLEncryptionDecryption():

    def enc(data : any):
        return signer.sign(data)


    def dec(data : any):
        try:
            return signer.unsign(data)
        except Exception as e:
            return None