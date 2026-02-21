import argparse
import mailbox
import os
import statistics
import time

from buscadores.pishing import BUSCADORES, Pishing
import utilidades


def _fmt_seconds(value):
    return f"{value:.4f}s"


def _load_messages(ruta_mbox, max_messages=None):
    mensajes = []
    mbox = mailbox.mbox(ruta_mbox)
    try:
        for idx, mensaje in enumerate(mbox):
            if max_messages is not None and idx >= max_messages:
                break
            mensajes.append(mensaje)
    finally:
        mbox.close()
    return mensajes


def benchmark_examinar(carpeta, archivo_mbox, phishing_label, repeats):
    tiempos = []
    total_filas = 0
    for _ in range(repeats):
        inicio = time.perf_counter()
        procesador = Pishing(carpeta, archivo_mbox, phishing_label)
        filas = procesador.examinar()
        duracion = time.perf_counter() - inicio
        tiempos.append(duracion)
        total_filas = len(filas)

    return {
        "repeats": repeats,
        "rows": total_filas,
        "runs": tiempos,
        "mean": statistics.mean(tiempos),
        "median": statistics.median(tiempos),
        "min": min(tiempos),
        "max": max(tiempos),
    }


def benchmark_por_buscador(ruta_mbox, max_messages=None):
    mensajes = _load_messages(ruta_mbox, max_messages=max_messages)
    if not mensajes:
        return {"messages": 0, "rows": []}

    tiempos = {b.getBuscadorTitulo(): 0.0 for b in BUSCADORES}
    positivos = {b.getBuscadorTitulo(): 0 for b in BUSCADORES}

    inicio_total = time.perf_counter()
    for mensaje in mensajes:
        # Calienta cache base por mensaje para simular flujo real.
        utilidades.getDatos_Dict(mensaje)
        for buscador in BUSCADORES:
            titulo = buscador.getBuscadorTitulo()
            t0 = time.perf_counter()
            valor = buscador.getBuscador(mensaje)
            tiempos[titulo] += time.perf_counter() - t0
            if valor:
                positivos[titulo] += 1
    total = time.perf_counter() - inicio_total

    filas = []
    for buscador in BUSCADORES:
        titulo = buscador.getBuscadorTitulo()
        filas.append(
            {
                "buscador": titulo,
                "time": tiempos[titulo],
                "positive": positivos[titulo],
            }
        )
    filas.sort(key=lambda x: x["time"], reverse=True)

    return {"messages": len(mensajes), "total": total, "rows": filas}


def _print_examinar_result(result):
    print("\n=== Benchmark examinar() ===")
    print(f"repeticiones: {result['repeats']}")
    print(f"filas generadas: {result['rows']}")
    for idx, run_time in enumerate(result["runs"], start=1):
        print(f"run {idx}: {_fmt_seconds(run_time)}")
    print(f"promedio: {_fmt_seconds(result['mean'])}")
    print(f"mediana: {_fmt_seconds(result['median'])}")
    print(f"min: {_fmt_seconds(result['min'])}")
    print(f"max: {_fmt_seconds(result['max'])}")
    if result["rows"] > 0:
        print(f"throughput promedio: {result['rows'] / result['mean']:.2f} mensajes/s")


def _print_buscadores_result(result):
    print("\n=== Benchmark por buscador ===")
    print(f"mensajes medidos: {result['messages']}")
    if result["messages"] == 0:
        print("sin mensajes para analizar")
        return
    print(f"tiempo total pipeline: {_fmt_seconds(result['total'])}")
    print(f"tiempo por mensaje (pipeline): {_fmt_seconds(result['total'] / result['messages'])}")
    print(f"{'Buscador':30} {'Tiempo':>10} {'Positivos':>10}")
    print("-" * 54)
    for row in result["rows"]:
        print(f"{row['buscador'][:30]:30} {_fmt_seconds(row['time']):>10} {row['positive']:>10}")


def main():
    inicio_total = time.perf_counter()
    parser = argparse.ArgumentParser(description="Benchmark de buscadores de phishing.")
    parser.add_argument("--carpeta", required=True, help="Carpeta donde esta el mbox.")
    parser.add_argument("--archivo", required=True, help="Nombre del archivo mbox.")
    parser.add_argument("--phishy", type=int, default=1, help="Etiqueta Phishy (0 o 1).")
    parser.add_argument("--repeats", type=int, default=3, help="Repeticiones para examinar().")
    parser.add_argument(
        "--max-messages",
        type=int,
        default=None,
        help="Limite de mensajes para benchmark por buscador.",
    )
    parser.add_argument(
        "--skip-examinar",
        action="store_true",
        help="Omite benchmark de examinar().",
    )
    parser.add_argument(
        "--skip-buscadores",
        action="store_true",
        help="Omite benchmark por buscador.",
    )
    args = parser.parse_args()

    carpeta = args.carpeta
    archivo = args.archivo
    ruta_mbox = os.path.join(carpeta, archivo)
    if not os.path.exists(ruta_mbox):
        raise FileNotFoundError(f"No existe el mbox: {ruta_mbox}")

    if not args.skip_examinar:
        result_examinar = benchmark_examinar(
            carpeta=carpeta,
            archivo_mbox=archivo,
            phishing_label=args.phishy,
            repeats=max(1, args.repeats),
        )
        _print_examinar_result(result_examinar)

    if not args.skip_buscadores:
        result_buscadores = benchmark_por_buscador(
            ruta_mbox=ruta_mbox,
            max_messages=args.max_messages if args.max_messages and args.max_messages > 0 else None,
        )
        _print_buscadores_result(result_buscadores)

    print(f"\nTiempo total benchmark: {_fmt_seconds(time.perf_counter() - inicio_total)}")


if __name__ == "__main__":
    main()
