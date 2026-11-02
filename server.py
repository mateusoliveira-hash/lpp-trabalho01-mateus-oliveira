import socketio

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, static_files={
    "/": "client/index.html",
    "/assets": "client/assets",      # mapa, tileset e sprites da vila
})

CUSTO = 50 # Valor de madeira gasto na construção de uma doca.
TEMPO_OBRA = 10 # Quantidade de segundos até a doca ficar pronta.
INTERVALO = 5 # Quantidade de segundos entre as produções automáticas.
MADEIRA_POR_BARCO = 10 # Madeira gasta para produzir um barco
BARCOS_ENCOMENDA = 3 # Barcos exigidos em cada encomenda
PRAZO_ENCOMENDA = 45 # Segundos para entregar encomenda
PAGAMENTO = 100 # Madeira recebida ao entregar a encomenda

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
    "em_obra":0, # docas em construção
    "barcos": 0, #recurso refinado, produzido pelas docas concluídas
    "encomenda": None, # None significa que não há encomenda em andamento
    "entregas": 0, # Número de entregas de barcos realizadas
    "expiradas":0 # Quantas encomendas expiraram o prazo de 45 segundos
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
    # ON vila.abertura_solicitada: o Mestre PEDE para abrir, o servidor decide se pode
    pedido = "vila.abertura_solicitada"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre pode abrir a temporada", pedido)
        return
    if estado["fase"] != "aguardando":
        await recusar(sid, "A temporada já foi aberta", pedido)
        return
    estado["fase"] = "aberta"
    sio.start_background_task(producao)
    # EMIT vila.iniciada para TODOS (sem to=): a fase mudou e todos precisam ver.
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
        # refino: cada doca concluída troca madeira por 1 barco, enquanto houver madeira.
        novos = 0
        for _ in range(estado["concluidas"]):
            if estado["madeira"] < MADEIRA_POR_BARCO:
                break
            estado["madeira"] -= MADEIRA_POR_BARCO
            estado["barcos"] += 1
            novos += 1

        # EMIT recurso.produzido para TODOS: o estoque mudou e ninguém precisa perguntar.
        # barcos_novos diz quantos barcos saíram neste ciclo (o cliente não calcula).
        await sio.emit("recurso.produzido", fato("temporizador", barcos_novos=novos))

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

@sio.on("vila.encerramento_solicitado")
async def encerrar_vila(sid, dados=None):
    # ON vila.encerramento_solicitado: o Mestre PEDE para encerrar, o servidor decide.
    pedido = "vila.encerramento_solicitado"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre pode encerrar a temporada", pedido)
        return
    if estado["fase"] != "aberta":
        await recusar(sid, "A temporada não está aberta", pedido)
        return
    estado["fase"] = "encerrada"
    estado["encomenda"] = None # Pela Spec, encomendas pendentes são descartadas
    # EMIT vila.encerrada para TODOS, a partir daqui, novos pedidos são recusados.
    await sio.emit("vila.encerrada", fato(pedido))

@sio.on("encomenda.criacao_solicitada")
async def aceitar_encomenda(sid, dados=None):
    # ON encomenda.criacao_solicitada: o Mestre PEDE, o servidor valida e decide.
    pedido = "encomenda.criacao_solicitada"
    if jogadores[sid]["papel"] != "mestre":
        motivo = "Só o Mestre pode aceitar encomendas"
    elif estado["fase"] != "aberta":
        motivo = "A temporada não está aberta"
    elif estado["encomenda"] is not None:
        motivo = "Já existe uma encomenda em andamento"
    else:
        motivo = None

    if motivo:
        await recusar(sid, motivo, pedido)
        return
    encomenda = {"barcos": BARCOS_ENCOMENDA, "prazo": PRAZO_ENCOMENDA}
    estado["encomenda"] = encomenda
    # EMIT encomenda.recebida para TODOS: todos precisam ver que há uma encomenda e seu prazo.
    await sio.emit("encomenda.recebida", fato(pedido))
    sio.start_background_task(prazo_encomenda, encomenda)

async def prazo_encomenda(encomenda):
    # Temporizador: é a passagem do tempo que gera evento, sem clique de ninguém
    await sio.sleep(PRAZO_ENCOMENDA)
    # Só expira se ESTA encomenda ainda estiver em andamento.
    if estado["encomenda"] is not encomenda:
        return
    estado["encomenda"] = None
    estado["expiradas"] += 1
    # EMIT encomenda.expirada para TODOS: a encomenda acabou sem pagamento.
    await sio.emit("encomenda.expirada", fato("encomenda.recebida (temporizador)"))

@sio.on("encomenda.entrega_solicitada")
async def entregar_encomenda(sid, dados=None):
    # ON encomenda.entrega_solicitada, o jogador PEDE, o servidor valida e decide.
    pedido = "encomenda.entrega_solicitada"
    # Sem await até alterar o estado, em uma disputa, só o primeiro pedido encontra a encomenda
    if estado["fase"] != "aberta":
        motivo = "A temporada não está aberta"
    elif estado["encomenda"] is None:
        motivo = "Não há encomenda para entregar"
    elif estado["barcos"] < BARCOS_ENCOMENDA:
        motivo = "Barcos insuficientes"
    else:
        motivo = None
    if motivo:
        await recusar(sid, motivo, pedido)
        return

    estado["barcos"] -= BARCOS_ENCOMENDA
    estado["madeira"] += PAGAMENTO
    estado["encomenda"] = None
    estado["entregas"] += 1
    # EMIT encomenda.entregue para TODOS, barcos, madeira e encomenda mudaram para todo mundo.
    await sio.emit("encomenda.entregue", fato(pedido, por=jogadores[sid]["nome"]))