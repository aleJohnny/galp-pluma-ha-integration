**Todo o código foi criado com Claude Sonet 5.5 Médio, fiz uma revisão e tenho a integração funcionando no meu Home Assistant com 3 botijas.**

# Galp Pluma para o Home Assistant

Integração não oficial que lê o **nível de gás (%)** e a **temperatura** das
garrafas Galp Pluma com Bluetooth, sem usar a app Mundo Galp nem a conta Galp.

> **Aviso:** projeto independente, sem qualquer ligação à Galp. O protocolo foi
> deduzido por engenharia inversa a partir de capturas Bluetooth de três
> garrafas do próprio autor. Use por sua conta e risco; pode deixar de
> funcionar se a Galp mudar o firmware.

## O que faz

- Descobre garrafas automaticamente (nome Bluetooth `Pluma…`).
- Suporta várias garrafas, cada uma como um dispositivo.
- Sensor **Nível de gás** (%). **Pode diferir da app em alguns pontos** (nas
  amostras, entre -3 e +2): ver [PROTOCOL.md](PROTOCOL.md).
- Sensor **Temperatura** (°C).
- Um sensor de diagnóstico desativado por defeito (`byte 7`), cujo significado
  ainda não se conhece.
- Funciona com o Bluetooth do próprio Home Assistant e com **proxies ESP32**.
- Tolera o *deep sleep* da garrafa: se uma leitura falhar, mantém o último valor
  e tenta de novo ao fim de 3 minutos (até 5 falhas seguidas, depois fica
  "indisponível").

## Instalação

1. Copie a pasta `custom_components/galp_pluma` para a pasta
   `custom_components` da configuração do Home Assistant (a que contém o
   `configuration.yaml`).
2. Reinicie o Home Assistant.
3. As garrafas ao alcance de um adaptador ou proxy Bluetooth aparecem em
   **Definições → Dispositivos e serviços** como descobertas. Se não aparecerem,
   use **Adicionar integração → Galp Pluma**.
4. Os dispositivos ficam com o nome "Pluma" mais 6 caracteres do endereço
   Bluetooth. Com várias garrafas, **renomeie-os** no Home Assistant (por
   exemplo "Pluma fogão"). O número do nome Bluetooth não coincide com o
   código impresso na garrafa, por isso não serve para as distinguir.

## Notas de utilização

- **Uma só ligação de cada vez:** a garrafa aceita um cliente. Se a app Galp
  (ou outro telemóvel) estiver ligada, a leitura falha. Não é preciso emparelhar
  a garrafa na app para usar esta integração.
- **Bateria:** cada leitura acorda a garrafa. O intervalo por defeito é de
  15 minutos (Opções da integração: 5 a 240). O nível de gás muda devagar, por
  isso não vale a pena ler com mais frequência.
- **Alcance:** a garrafa tem de estar ao alcance de um adaptador ou proxy que
  suporte ligações ativas (os proxies ESP32 com `active: true`, o valor
  habitual do ESPHome). Sinais fracos (por volta de -85 dBm) dão ligações
  instáveis: ponha um proxy mais perto.
- **Privacidade:** o nome Bluetooth, o endereço MAC, o código do QR e o link NFC
  identificam a sua garrafa. Não os partilhe em publicações públicas.

## Detalhes técnicos

Ver [PROTOCOL.md](PROTOCOL.md).

## Testes

```
pip install pytest
pytest tests
```

Os testes do protocolo usam as frames reais capturadas e não precisam do Home
Assistant.
