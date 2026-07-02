# %%
import os
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

ID_SHEET = "1560251994"

SHEETS = {
    "JV": "1snfOUctmalpe-RdlHzGWg14q8N6LVLuAqW2btkyWgEQ",
    "RICARDO": "1g-7UEZiLS8cgTwlNLNNVXjxLiokevGQ2kzaiybfDQPo",
    "ALEKS": "1-ggf1gOtys8GLEmh5rHSSKODJlE-wXbILDy6Ccfk7eM",
    "TOLEDO": "1BpN71IgdovOiHZlA5x4e5S66nQ9-2zBfDUDhLcrYZcI",
    "PAULO": "1NKMj_uhz7g7DOvY2gKOMapCwkWTSEGCb1gB8qVoq89U",
}

def get_engine():

    DATABASE_URL = os.getenv("DATABASE_URL")

    return create_engine(
        DATABASE_URL,
        pool_pre_ping=True
    )


def get_url(sheet_id, gid):
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx&gid={gid}"
    )


columns_rename = {
    "Valor Contrato (R$)": "Valor Contrato",
    "MRR (R$)": "Valor Mensal",
    "Dias p/ Vencer": "Vencimento",
}

dfs = []

for profit, sheet_id in SHEETS.items():

    df = pd.read_excel(get_url(sheet_id, ID_SHEET))

    # Cabeçalho
    df.columns = df.iloc[2]
    df = df.iloc[3:].reset_index(drop=True)

    df.columns.name = None
    df.columns = df.columns.str.strip()

    df.rename(columns=columns_rename, inplace=True)

    df.drop(
        columns=[
            "Sem. 1",
            "Sem. 2 ",
            "Sem. 2",
            "Sem. 3",
            "Sem. 4",
            "Observação",
        ],
        errors="ignore",
        inplace=True,
    )

    # Remove clientes vazios
    df["Cliente"] = df["Cliente"].fillna("").astype(str).str.strip()
    df["Franquia"] = df["Franquia"].fillna("").astype(str).str.strip()

    df = df[
        (df["Cliente"] != "")
        & (df["Franquia"] != "")
    ]

    ####################################################
    # LIMPEZA DOS VALORES
    ####################################################

    # Monetários
    for coluna in ["Valor Contrato", "Valor Mensal"]:

        df[coluna] = (
            df[coluna]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.replace("R$", "", regex=False)
            .str.strip()
        )

        df[coluna] = pd.to_numeric(
            df[coluna],
            errors="coerce"
        )

    ####################################################
    # DATAS
    ####################################################

    for coluna in ["Início Contrato", "Fim Contrato"]:

        df[coluna] = (
            df[coluna]
            .replace(
                [
                    "#VALOR!",
                    "Recorrente",
                    "",
                    "nan"
                ],
                np.nan
            )
        )

        df[coluna] = pd.to_datetime(
            df[coluna],
            errors="coerce",
            dayfirst=True
        )

    ####################################################
    # VENCIMENTO
    ####################################################

    df["Vencimento"] = (
        df["Vencimento"]
        .replace(
            [
                "Recorrente",
                "#VALOR!",
                "",
                "nan"
            ],
            np.nan
        )
    )

    df["Vencimento"] = pd.to_numeric(
        df["Vencimento"],
        errors="coerce"
    )

    # Corrige datas inválidas que aparecem como -46205
    df.loc[
        df["Vencimento"] < -1000,
        "Vencimento"
    ] = np.nan

    ####################################################
    # COLUNAS AUXILIARES
    ####################################################

    hoje = pd.Timestamp.today().normalize()

    df["Cliente Ativo"] = (
        df["Status"]
        .astype(str)
        .str.upper()
        .eq("ATIVO")
    )

    df["Cliente Churn"] = (
        df["Status"]
        .astype(str)
        .str.upper()
        .eq("CHURN")
    )

    df["Cliente Pausado"] = (
        df["Status"]
        .astype(str)
        .str.upper()
        .eq("PAUSADO")
    )

    df["Ano"] = df["Início Contrato"].dt.year

    df["Mês"] = df["Início Contrato"].dt.month

    df["Nome Mês"] = df["Início Contrato"].dt.month_name(locale="pt_BR")

    df["AnoMês"] = (
        df["Início Contrato"]
        .dt.to_period("M")
        .astype(str)
    )

    df["Meses Contrato"] = (
        (
            hoje - df["Início Contrato"]
        ).dt.days / 30.44
    ).round(1)

    ####################################################
    # FAIXA DE VENCIMENTO
    ####################################################

    def faixa_vencimento(v):

        if pd.isna(v):
            return "Recorrente"

        if v < 0:
            return "Vencido"

        if v <= 30:
            return "Até 30 dias"

        if v <= 60:
            return "31 a 60 dias"

        if v <= 90:
            return "61 a 90 dias"

        return "Mais de 90 dias"

    df["Faixa Vencimento"] = df["Vencimento"].apply(faixa_vencimento)

    ####################################################
    # PROFIT
    ####################################################

    df["Profit"] = profit

    dfs.append(df)

####################################################
# DATAFRAME FINAL
####################################################

clientes = pd.concat(
    dfs,
    ignore_index=True
)

####################################################
# ORDENAÇÃO
####################################################

clientes.sort_values(
    [
        "Profit",
        "Franquia",
        "Cliente"
    ],
    inplace=True
)

clientes.reset_index(
    drop=True,
    inplace=True
)

####################################################
# EXPORTAÇÃO
####################################################

engine = get_engine()

dt.to_sql(
    "clientes_franqueados_profits",
    engine,
    if_exists="replace",
    index=False
)