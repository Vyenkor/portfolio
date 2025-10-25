# portfolio
项目介绍：Portfolio Aggregator
项目概述

本项目是一个简单的投资数据聚合器，用于定时从第三方接口获取基金和加密货币的行情信息，并将最新价格和历史数据保存到仓库中。项目使用 GitHub Actions 自动运行脚本，生成 CSV 文件，方便通过 Excel 或其他工具实时查看资产净值、收益率等信息。

目录结构说明

项目根目录包含以下主要子目录与文件：

config/

assets.json：资产配置文件，用于列出需要跟踪的基金代码、加密货币名称以及计价币种。修改该文件即可增删要监控的标的，脚本会自动读取并生成对应数据。文件格式示例如下：

{
  "funds": ["017436", "001186"],
  "coins": ["bitcoin", "ethereum", "tether"],
  "vs": ["cny", "usd"]
}


字段说明：

funds：需要获取数据的基金代码列表，使用天天基金的 6 位基金代码。

coins：需要获取价格的加密货币名称，使用 CoinGecko 的 ID（如 bitcoin、ethereum 等）。

vs：计价币种列表，例如 cny 或 usd，脚本会对每个币种生成报价。

src/

aggregate.py：数据聚合脚本，使用 requests 库从第三方接口拉取数据并生成 CSV 文件。脚本会读取 config/assets.json 中的基金代码和加密货币信息：

通过 DoctorXiong
 接口或天天基金页面接口获取基金的最新净值（nav）、估算净值（est_nav）和 24 小时估算涨跌幅（est_chg_24h_pct）。如果 DoctorXiong 接口不可用，则回退至天天基金 fundgz API。

通过 CoinGecko
 的 /coins/markets 接口获取加密货币的现价 (current_price) 及多周期涨跌幅（1h、24h、7d、30d 等）。

生成两个 CSV：

data/agg_latest.csv：最新快照，包含基金和加密货币的最新价格和估算涨跌幅。

data/history.csv：历史数据累积表，脚本运行时会在该文件末尾追加一行，保存时间戳、标的价格和涨跌幅，供长期追踪。

脚本的核心流程如下：

读取 config/assets.json 获取基金代码、加密货币 ID 和计价币种列表。

使用 DoctorXiong API 和天天基金备选接口获取基金数据。

使用 CoinGecko API 获取加密货币价格和涨跌幅。

生成最新行情 CSV (agg_latest.csv) 并追加到历史 CSV (history.csv)。

在本地运行该脚本或由 GitHub Actions 定时运行即可生成最新数据文件。

.github/workflows/

daily-fetch.yml：GitHub Actions 工作流文件，用于设置自动化任务。工作流配置了以下功能：

使用定时器（cron）每天或每小时运行 src/aggregate.py 脚本，从第三方接口抓取数据并更新仓库的 CSV 文件。

自动安装依赖（通过 pip install）并运行脚本。

如果生成的数据文件发生变化，工作流会自动提交并推送到仓库。

通过编辑此文件，可以调整任务运行频率，例如每小时、每天或每周运行一次。也可以通过 workflow_dispatch 手动触发。

data/

此目录用于存放脚本生成的数据文件：

agg_latest.csv：最新数据快照，每次脚本运行时覆盖更新。文件包含每个基金和加密货币的最新价格、净值日期、估算涨跌幅以及时间戳。

history.csv：历史数据文件，脚本每次运行时在该文件末尾追加一行记录，包含时间戳、标的类型、标的 ID、价格和涨跌幅等信息，可用于长期分析。

.gitkeep：空文件，用于确保空目录被纳入版本控制（git 会忽略空目录，因此通过添加 .gitkeep 保持目录存在）。

requirements.txt

列出了项目的 Python 依赖包。目前仅包含 requests 库，用于执行 HTTP 请求。如果将来添加其他第三方库，应在此文件中列出。

使用说明

修改 config/assets.json 根据你的需求添加或删除基金代码和加密货币 ID，指定需要的计价币种。

在本地环境中执行 python src/aggregate.py 以生成数据文件，或通过 GitHub Actions 自动运行脚本。

在 Excel 或其他分析工具中读取 data/agg_latest.csv 查看最新行情，或者读取 data/history.csv 进行历史趋势分析。

若需要增加新的依赖库，请在 requirements.txt 中添加，并在 GitHub Actions 工作流中安装。

该项目作为模板，可根据实际需要扩展，例如增加其它 API 源、加入通知或告警机制，或将数据同步至数据库等。希望该项目能帮助你快速搭建自己的投资数据聚合系统。
