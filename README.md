# Disclaimer uso de AI
- Todo o código da integração (engenharia reversa e a integração em si) foi criado com Claude Sonet 5.5 Médio.
- Embora eu não seja letrado em Python, fiz uma revisão do código e tenho a integração funcionando no meu Home Assistant com 3 botijas.
- Usei DeepSeek 4.1 Flash para me ajudar a ajustar a integração com ícone (branding) e ser instalável pelo HACS (Marketplace).

# Disclaimer de uso de marca Galp
- Logos e nomes da Galp, Pluma são propriedade da GALP ENERGIA, S.A. e utilizados usando os assets disponíveis na internet respeitando a uso da marca.

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
- **Intervalo de leitura por garrafa**, de 5 minutos a 30 dias, ou só manual
  (ver [Intervalo por garrafa](#intervalo-por-garrafa)).
- Botão **Atualizar agora** (lê já) e sensor de diagnóstico **Última leitura**.
- Tolera o *deep sleep* da garrafa: se uma leitura falhar, mantém o último valor
  e tenta de novo ao fim de 3 minutos (5 vezes), depois de hora a hora (ou no
  intervalo da garrafa, se for mais curto). Os sensores só ficam "indisponíveis"
  quando a última leitura boa tem mais de 2 × o intervalo (e no mínimo 1 hora).

## Instalação

### Marketplace (aka HACS)

Use o link abaixo para ir direto para o repositório no Marketplace (aka HACS):

[![Abra sua instância do Home Assistant e abra o repositório dentro do Marktplace (aka HACS).](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alejohnny&repository=galp-pluma-ha-integration)

_ou_

1. Abra o HACS (ou Marketplace se você está usando 2026.11) > Add from Link ou menu com 3 pontos (canto superior direito) > **Custom repositories**.
2. Adicione `https://github.com/aleJohnny/galp-pluma-ha-integration` com categoria **Integration**.
3. Procure por "Galp Pluma" no HACS, instale e reinicie o Home Assistant.

### Manual

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

-   <img width="1064" height="759" alt="image" src="https://github.com/user-attachments/assets/c5b5b33a-c1c3-4bb5-8416-e62854d03153" />
-   <img width="1280" height="583" alt="image" src="https://github.com/user-attachments/assets/4cc0600e-cb1f-49b1-a65f-35b4f16d5ef7" />
-   <img width="1280" height="579" alt="image" src="https://github.com/user-attachments/assets/f80ca782-86f5-48d2-8bf9-d13b00fc701c" />
-

## Intervalo por garrafa

Cada garrafa tem o seu intervalo entre leituras, em minutos: de 5 a 43200 (30
dias), ou **0 para só ler manualmente**. Muda-se de duas formas, que ficam
sempre iguais:

- a entidade **Intervalo de leitura** do dispositivo (um `number`, na secção de
  configuração), que também se pode usar em automatismos;
- **Configurar** na página da integração.

A alteração vale logo, sem recarregar a integração nem acordar a garrafa: a
leitura seguinte é agendada a partir desse momento. Para ler já, use o botão
**Atualizar agora**. O valor guarda-se e sobrevive a reinícios (em cada arranque
do Home Assistant faz-se sempre uma leitura).

Referências: 60 = 1 hora, 360 = 6 horas, 1440 = 1 dia, 10080 = 1 semana.

### Exemplo: duas botijas de butano, uma em uso e outra de reserva

Com um auxiliar `input_select.butano_em_uso` com as opções `"1"` e `"2"`, a que
estiver em uso lê-se todos os dias e a de reserva uma vez por semana. Ao mudar
a seleção, a que passa a estar em uso é lida logo. (Exemplo **não testado**; os
nomes das entidades dependem do nome que der aos dispositivos e do idioma, por
isso confirme-os em Definições → Entidades.)

```yaml
alias: Intervalos das botijas de butano
triggers:
  - trigger: state
    entity_id: input_select.butano_em_uso
actions:
  - choose:
      - conditions:
          - condition: state
            entity_id: input_select.butano_em_uso
            state: "1"
        sequence:
          - action: number.set_value
            target:
              entity_id: number.butano_1_intervalo_de_leitura
            data:
              value: 1440
          - action: number.set_value
            target:
              entity_id: number.butano_2_intervalo_de_leitura
            data:
              value: 10080
          - action: button.press
            target:
              entity_id: button.butano_1_atualizar_agora
    default:
      - action: number.set_value
        target:
          entity_id: number.butano_2_intervalo_de_leitura
        data:
          value: 1440
      - action: number.set_value
        target:
          entity_id: number.butano_1_intervalo_de_leitura
        data:
          value: 10080
      - action: button.press
        target:
          entity_id: button.butano_2_atualizar_agora
mode: single
```

## Notas de utilização

- **Uma só ligação de cada vez:** a garrafa aceita um cliente. Se a app Galp
  (ou outro telemóvel) estiver ligada, a leitura falha. Não é preciso emparelhar
  a garrafa na app para usar esta integração.
- **Bateria:** cada leitura acorda a garrafa. O intervalo por defeito é de
  15 minutos, e cada garrafa pode ter o seu. O nível de gás muda devagar, por
  isso intervalos de horas ou dias chegam para a maioria dos casos.
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
