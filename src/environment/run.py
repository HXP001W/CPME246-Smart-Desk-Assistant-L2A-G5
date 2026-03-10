# run.py 智能环境控制系统 一键启动脚本
from app import app

if __name__ == '__main__':
    print("="*60)
    print("          智能环境控制系统 一键启动")
    print("="*60)
    # 启动Web服务和控制器
    app.run(host='0.0.0.0', port=5000, debug=False)
