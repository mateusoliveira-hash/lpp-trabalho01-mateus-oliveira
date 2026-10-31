import socketio

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, static_files={
    "/": "client/index.html",
    "/assets": "client/assets",      # mapa, tileset e sprites da vila
})

# A partir da Etapa 1, adicione o seu código ABAIXO desta linha.
CUSTO = 50 # Valor de madeira gasto na construção de uma doca.
TEMPO_OBRA = 10 # Quantidade de segundos até a doca ficar pronta.
INTERVALO = 5 # Quantidade de segundos entre as produções automáticas.

estado = {
    "fase": "aguardando", # aguardando, aberta, encerrada
    "madeira": 150,
    "carpinteiros":0, # quantos carpinteiros estão ocupados agora
    "limite": 3, # maximo de carpinteiros
    "producao": 15, # madeira produzida a cada intervalo
    "intervalo": INTERVALO,
    "tempo_obra": TEMPO_OBRA,
    "custo": CUSTO,
    "concluidas": 0, # docas prontas
    "em_obra":0 # docas em construção
}

jogadores = {} # sid {"nome", "papel"}

def fato(causa, **extras):
    # Monta o payload de um FATO: o estado atual, a CAUSA (o evento ou o temporizador que gerou o fato) e dados extras
    return {"estado": dict(estado), "causa": causa, **extras}

@sio.event
async def connect(sid, environ, auth):
    auth = auth or {}
    jogadores[sid] = {
        "nome": auth.get("nome", "Anônimo"),
        "papel": auth.get("papel", "jogador"),
    }
    # EMIT estado.sincronizado só para quem acabou de entrar (to=sid):
    # os outros já têm o estado, o recém-chegado precisa dele para desenhar o estaleiro.
    await sio.emit("estado.sincronizado", fato("conexao"), to=sid)

@sio.event
async def disconnect(sid):
    jogadores.pop(sid, None)


async def recusar(sid, motivo, causa):
    # EMIT operacao.recusada só para quem pediu (to=sid): a recusa não muda
    # o estado, então para os outros participantes não tem nada para atualizar
    await sio.emit("operacao.recusada", {"motivo":motivo, "causa": causa}, to=sid)

@sio.on("vila.abertura_solicitada")
async def abrir_vila(sid, dados=None):
    # ON vila.abertura_solicitada: o Mestre PEDE para abrir, o servidor decide de pode
    pedido = "vila.abertura_solicitada"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre pode abrir a temporada", pedido)
        return
    if estado["fase"] != "aguardando":
        await recusar(sid, "A temporada já foi aberta", pedido)
        return
    estado["fase"] = "aberta"
    sio.start_background_task(producao)
    # EMIT vila.iniciada para TODOS (sem to=): a fase mudou e todos precisa ver.
    await sio.emit("vila.iniciada", fato(pedido))


@sio.on("construcao.solicitada")
async def construir(sid, dados=None):
    # ON construcao.solicitada, o jogador PEDE uma doca, o servidor valida e decide.
    pedido = "construcao.solicitada"
    # Valida TUDO antes de alterar o estado, sem nenhum await no meio.
    # Assim dois pedidos simultâneos são decididos um de cada vez, sem condição de corrida.
    if estado["fase"] != "aberta":
        motivo = "A temporada não está aberta"
    elif estado["madeira"] < CUSTO:
        motivo = "Madeira insuficiente"
    elif estado["carpinteiros"] >= estado["limite"]:
        motivo = "Sem carpinteiro livre"
    else:
        motivo = None

    if motivo:
        await recusar(sid, motivo, pedido)
        return

    estado["madeira"] -= CUSTO
    estado["carpinteiros"] += 1
    estado["em_obra"] += 1
    nome = jogadores[sid]["nome"]
    # EMIT construcao.iniciada para TODOS: madeira e carpinteiros mudaram para todo mundo.
    # "por" diz quem pediu, para os outros saberem quem iniciou a obra. 
    await sio.emit("construcao.iniciada", fato(pedido, por=nome)) 
    sio.start_background_task(obra, nome)

async def producao():
    #Temporizador: é uma FONTE de eventos, sem clique de ninguém.
    while estado["fase"] == "aberta":
        # sio.sleep libera o laço de eventos, time.sleep travaria o servidor inteiro.
        await sio.sleep(INTERVALO)
        # A temporada pode ter sido encerrada durante a espera.
        if estado["fase"] != "aberta":
            break
        estado["madeira"] += estado["producao"]
        # EMIT recurso.produzido para TODOS: o estoque mudou e ninguém precisa perguntar.
        await sio.emit("recurso.produzido", fato("temporizador"))

async def obra(nome):
    # Temporizador de uma doca: roda em segundo plano, separado do pedido.
    await sio.sleep(TEMPO_OBRA)
    # Pela spec, obras em andamento não terminam depois do encerramento.
    if estado["fase"] != "aberta":
        return
    estado["carpinteiros"] -= 1
    estado["em_obra"] -= 1
    estado["concluidas"] += 1
    causa = "construcao.iniciada (temporizador)"

    # EMIT construcao.concluida para TODOS: o carpinteiro ficou livre e há uma doca nova
    await sio.emit("construcao.concluida", fato(causa, por=nome))