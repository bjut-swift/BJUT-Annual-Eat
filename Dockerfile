FROM python:3.10-slim

WORKDIR /app

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/bjut_annual_eat ./src/bjut_annual_eat

RUN mkdir -p cache output src/bjut_annual_eat/fonts && \
    apt-get update && \
    apt-get install -y curl vim && \
    curl -L https://raw.githubusercontent.com/StellarCN/scp_zh/master/fonts/SimHei.ttf \
         -o src/bjut_annual_eat/fonts/SimHei.ttf && \
    apt-get remove -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app/src

CMD ["python", "-c", "from bjut_annual_eat.stat import analyze_consumption; analyze_consumption()"]