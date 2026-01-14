"""几何建模数据结构定义"""
from typing import Literal, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class GeometryShape(BaseModel):
    """几何形状定义"""
    
    type: Literal["rectangle", "circle", "ellipse"] = Field(
        ..., description="几何形状类型"
    )
    
    parameters: Dict[str, float] = Field(
        ..., description="形状参数，如矩形的宽高、圆的半径等"
    )
    
    position: Dict[str, float] = Field(
        default={"x": 0.0, "y": 0.0},
        description="形状位置坐标 (x, y)"
    )
    
    name: str = Field(
        default="",
        description="形状名称（可选）"
    )
    
    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, v: Dict[str, float], info) -> Dict[str, float]:
        """验证参数是否合理"""
        shape_type = info.data.get("type")
        
        if shape_type == "rectangle":
            if "width" not in v or "height" not in v:
                raise ValueError("矩形需要 width 和 height 参数")
            if v["width"] <= 0 or v["height"] <= 0:
                raise ValueError("矩形的宽高必须大于 0")
        
        elif shape_type == "circle":
            if "radius" not in v:
                raise ValueError("圆形需要 radius 参数")
            if v["radius"] <= 0:
                raise ValueError("圆的半径必须大于 0")
        
        elif shape_type == "ellipse":
            if "a" not in v or "b" not in v:
                raise ValueError("椭圆需要 a (长轴) 和 b (短轴) 参数")
            if v["a"] <= 0 or v["b"] <= 0:
                raise ValueError("椭圆的长轴和短轴必须大于 0")
        
        return v
    
    @field_validator("position")
    @classmethod
    def validate_position(cls, v: Dict[str, float]) -> Dict[str, float]:
        """验证位置坐标"""
        if "x" not in v:
            v["x"] = 0.0
        if "y" not in v:
            v["y"] = 0.0
        return v


class GeometryPlan(BaseModel):
    """几何建模计划"""
    
    shapes: List[GeometryShape] = Field(
        ..., description="几何形状列表"
    )
    
    units: str = Field(
        default="m",
        description="单位（默认：米）"
    )
    
    model_name: str = Field(
        default="geometry_model",
        description="模型名称"
    )
    
    @field_validator("shapes")
    @classmethod
    def validate_shapes(cls, v: List[GeometryShape]) -> List[GeometryShape]:
        """验证形状列表不为空"""
        if not v:
            raise ValueError("至少需要一个几何形状")
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "model_name": self.model_name,
            "units": self.units,
            "shapes": [shape.model_dump() for shape in self.shapes]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeometryPlan":
        """从字典创建实例"""
        return cls(**data)
