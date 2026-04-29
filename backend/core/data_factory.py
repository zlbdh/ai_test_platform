# -*- coding: utf-8 -*-
"""
Data Factory - 测试数据生成工厂
基于 Faker 库生成各种测试数据
"""
from typing import Dict, Any, List, Optional
from faker import Faker
import random
import string


class DataFactory:
    """测试数据生成工厂"""
    
    def __init__(self, locale: str = "zh_CN"):
        """
        初始化数据工厂
        
        Args:
            locale: 地区设置，默认中文
        """
        self.fake = Faker(locale)
        Faker.seed(None)  # 每次随机
        
        # 预定义的数据生成器映射
        self._generators = {
            # 个人信息
            "name": self.fake.name,
            "first_name": self.fake.first_name,
            "last_name": self.fake.last_name,
            "phone": self.fake.phone_number,
            "phone_number": self.fake.phone_number,
            "email": self.fake.email,
            "ssn": self.fake.ssn,
            "id_card": self.fake.ssn,
            
            # 地址
            "address": self.fake.address,
            "city": self.fake.city,
            "province": self.fake.province,
            "street_address": self.fake.street_address,
            "postcode": self.fake.postcode,
            
            # 公司
            "company": self.fake.company,
            "job": self.fake.job,
            
            # 网络
            "url": self.fake.url,
            "domain": self.fake.domain_name,
            "ip": self.fake.ipv4,
            "user_agent": self.fake.user_agent,
            
            # 文本
            "text": self.fake.text,
            "sentence": self.fake.sentence,
            "paragraph": self.fake.paragraph,
            "word": self.fake.word,
            
            # 日期时间
            "date": lambda: self.fake.date(),
            "datetime": lambda: self.fake.date_time().isoformat(),
            "time": lambda: self.fake.time(),
            "year": lambda: str(self.fake.year()),
            "month": lambda: str(self.fake.month()),
            
            # 数字
            "integer": lambda: random.randint(1, 1000),
            "float": lambda: round(random.uniform(0, 1000), 2),
            "price": lambda: round(random.uniform(10, 9999), 2),
            
            # 其他
            "uuid": self.fake.uuid4,
            "password": lambda: self.fake.password(length=12),
            "username": self.fake.user_name,
        }
    
    def generate(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据模板生成单条数据
        
        Args:
            template: 数据模板，key 为字段名，value 为数据类型
                      例如: {"name": "name", "phone": "phone_number"}
        
        Returns:
            生成的数据字典
        """
        result = {}
        for field_name, data_type in template.items():
            if isinstance(data_type, str):
                # 数据类型是字符串，从预定义生成器查找
                generator = self._generators.get(data_type)
                if generator:
                    result[field_name] = generator()
                else:
                    # 未知类型，使用原值
                    result[field_name] = data_type
            elif isinstance(data_type, dict):
                # 嵌套模板
                result[field_name] = self.generate(data_type)
            elif isinstance(data_type, list) and len(data_type) > 0:
                # 从列表中随机选择
                result[field_name] = random.choice(data_type)
            else:
                # 保持原值
                result[field_name] = data_type
        
        return result
    
    def generate_batch(self, template: Dict[str, Any], count: int = 10) -> List[Dict[str, Any]]:
        """
        批量生成数据
        
        Args:
            template: 数据模板
            count: 生成数量
        
        Returns:
            数据列表
        """
        return [self.generate(template) for _ in range(count)]
    
    def get_available_types(self) -> List[str]:
        """获取所有可用的数据类型"""
        return list(self._generators.keys())


# 全局单例
_factory: Optional[DataFactory] = None


def get_data_factory(locale: str = "zh_CN") -> DataFactory:
    """获取数据工厂单例"""
    global _factory
    if _factory is None:
        _factory = DataFactory(locale)
    return _factory


# 便捷函数
def generate_test_data(template: Dict[str, Any]) -> Dict[str, Any]:
    """生成单条测试数据"""
    return get_data_factory().generate(template)


def generate_test_data_batch(template: Dict[str, Any], count: int = 10) -> List[Dict[str, Any]]:
    """批量生成测试数据"""
    return get_data_factory().generate_batch(template, count)
