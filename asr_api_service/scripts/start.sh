#!/bin/bash

# ASR API Service 启动脚本
# 用于快速启动开发或生产环境

set -e

# 脚本配置
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
ENV_FILE="$PROJECT_DIR/.env"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Python版本
check_python() {
    log_info "检查Python版本..."
    
    if command -v python3.11 &> /dev/null; then
        PYTHON_CMD=python3.11
    elif command -v python3 &> /dev/null; then
        PYTHON_CMD=python3
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        if [[ "$PYTHON_VERSION" < "3.9" ]]; then
            log_error "需要Python 3.9或更高版本，当前版本: $PYTHON_VERSION"
            exit 1
        fi
    else
        log_error "未找到Python 3.9+。请先安装Python。"
        exit 1
    fi
    
    log_success "Python版本检查通过: $($PYTHON_CMD --version)"
}

# 创建虚拟环境
setup_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        log_info "创建Python虚拟环境..."
        $PYTHON_CMD -m venv "$VENV_DIR"
        log_success "虚拟环境创建成功"
    else
        log_info "虚拟环境已存在，跳过创建"
    fi
    
    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"
    
    # 升级pip
    log_info "升级pip..."
    pip install --upgrade pip
}

# 安装依赖
install_dependencies() {
    log_info "安装项目依赖..."
    
    # 确保在虚拟环境中
    source "$VENV_DIR/bin/activate"
    
    # 安装项目
    pip install -e .
    
    # 检查是否需要开发依赖
    if [[ "$1" == "dev" ]] || [[ "$1" == "development" ]]; then
        log_info "安装开发依赖..."
        pip install -e ".[dev]"
    fi
    
    log_success "依赖安装完成"
}

# 检查环境配置
check_env_config() {
    if [ ! -f "$ENV_FILE" ]; then
        log_warning "环境配置文件 .env 不存在"
        
        if [ -f "$PROJECT_DIR/.env.example" ]; then
            log_info "从 .env.example 复制配置文件..."
            cp "$PROJECT_DIR/.env.example" "$ENV_FILE"
            log_warning "请编辑 .env 文件设置API密钥等配置"
            log_info "主要需要设置的配置:"
            echo "  - ASR_PROVIDER (选择: fireworks, openai, whisper)"
            echo "  - FIREWORKS_API_KEY 或 OPENAI_API_KEY"
            echo "  - SECRET_KEY (生产环境)"
        else
            log_error "找不到 .env.example 模板文件"
            exit 1
        fi
    else
        log_success "环境配置文件存在"
        
        # 检查关键配置
        if ! grep -q "API_KEY" "$ENV_FILE"; then
            log_warning "请确保设置了相应的API密钥"
        fi
    fi
}

# 创建数据目录
setup_directories() {
    log_info "创建数据目录..."
    
    mkdir -p "$PROJECT_DIR/data/audio"
    mkdir -p "$PROJECT_DIR/data/logs"
    mkdir -p "$PROJECT_DIR/data/temp"
    
    log_success "数据目录创建完成"
}

# 检查TEN-VAD
check_ten_vad() {
    TEN_VAD_PATH="$PROJECT_DIR/../ten-vad"
    
    if [ -d "$TEN_VAD_PATH" ]; then
        log_success "TEN-VAD库已找到"
    else
        log_warning "未找到TEN-VAD库，将使用简单VAD fallback"
        log_info "如需使用TEN-VAD，请确保 ../ten-vad/ 目录存在"
    fi
}

# 启动服务
start_service() {
    local mode="$1"
    
    # 确保在虚拟环境中
    source "$VENV_DIR/bin/activate"
    
    log_info "启动ASR API Service..."
    log_info "模式: $mode"
    
    case "$mode" in
        "dev"|"development")
            log_info "启动开发服务器 (auto-reload enabled)"
            asr-api serve --reload --host 0.0.0.0 --port 8000
            ;;
        "prod"|"production")
            log_info "启动生产服务器"
            asr-api serve --host 0.0.0.0 --port 8000 --workers 4
            ;;
        *)
            log_info "启动默认服务器"
            asr-api serve
            ;;
    esac
}

# 显示帮助信息
show_help() {
    echo "ASR API Service 启动脚本"
    echo ""
    echo "用法: $0 [选项] [模式]"
    echo ""
    echo "选项:"
    echo "  -h, --help     显示此帮助信息"
    echo "  -s, --setup    仅进行环境设置，不启动服务"
    echo "  -c, --check    检查环境配置"
    echo ""
    echo "模式:"
    echo "  dev            开发模式 (auto-reload)"
    echo "  prod           生产模式 (多worker)"
    echo "  默认           标准模式"
    echo ""
    echo "示例:"
    echo "  $0              # 设置环境并启动标准服务"
    echo "  $0 dev          # 设置环境并启动开发服务"
    echo "  $0 prod         # 设置环境并启动生产服务"
    echo "  $0 --setup      # 仅设置环境"
    echo "  $0 --check      # 检查环境配置"
}

# 检查环境
check_environment() {
    log_info "环境检查报告"
    echo "=================="
    
    # Python版本
    if command -v python3 &> /dev/null; then
        echo "✅ Python: $(python3 --version)"
    else
        echo "❌ Python: 未安装"
    fi
    
    # 虚拟环境
    if [ -d "$VENV_DIR" ]; then
        echo "✅ 虚拟环境: 已创建"
    else
        echo "❌ 虚拟环境: 未创建"
    fi
    
    # 环境配置
    if [ -f "$ENV_FILE" ]; then
        echo "✅ 环境配置: 已存在"
        
        # 检查API密钥
        if grep -q "your.*api.*key" "$ENV_FILE"; then
            echo "⚠️  API密钥: 需要配置"
        else
            echo "✅ API密钥: 已配置"
        fi
    else
        echo "❌ 环境配置: 未配置"
    fi
    
    # TEN-VAD
    if [ -d "$PROJECT_DIR/../ten-vad" ]; then
        echo "✅ TEN-VAD: 可用"
    else
        echo "⚠️  TEN-VAD: 不可用 (将使用fallback)"
    fi
    
    echo "=================="
}

# 主函数
main() {
    cd "$PROJECT_DIR"
    
    local setup_only=false
    local check_only=false
    local mode="default"
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -s|--setup)
                setup_only=true
                shift
                ;;
            -c|--check)
                check_only=true
                shift
                ;;
            dev|development|prod|production)
                mode="$1"
                shift
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 显示横幅
    echo ""
    echo "🎤 ASR API Service 启动脚本"
    echo "================================"
    echo ""
    
    # 仅检查环境
    if [[ "$check_only" == true ]]; then
        check_environment
        exit 0
    fi
    
    # 环境设置
    log_info "开始环境设置..."
    check_python
    setup_venv
    install_dependencies "$mode"
    check_env_config
    setup_directories
    check_ten_vad
    
    log_success "环境设置完成!"
    
    # 如果只是设置环境，则退出
    if [[ "$setup_only" == true ]]; then
        log_info "环境设置完成，使用 '$0 $mode' 启动服务"
        exit 0
    fi
    
    echo ""
    log_info "准备启动服务..."
    echo "访问地址: http://localhost:8000"
    echo "API文档: http://localhost:8000/docs"
    echo "健康检查: http://localhost:8000/health"
    echo ""
    echo "按 Ctrl+C 停止服务"
    echo ""
    
    # 启动服务
    start_service "$mode"
}

# 错误处理
trap 'log_error "脚本执行失败"; exit 1' ERR

# 执行主函数
main "$@"