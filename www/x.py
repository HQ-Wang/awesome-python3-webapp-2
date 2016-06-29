async def test(request):
    params = await request.json()
    print(params)