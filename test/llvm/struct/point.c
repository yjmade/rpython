struct Point
{
    int x_;
    int y_;
};


void Point_init( struct Point *p, int x, int y )
{
    p->x_ = x;
    p->y_ = y;
}


void Point_move( struct Point *p, int dx, int dy )
{
    p->x_ += dx;
    p->y_ += dy;
}

int main(int argc, char **argv) {
    struct Point point;
    point.x_ = 128;
    point.y_ = 65536;
    Point_init( &point, 16, 32 );
    Point_move( &point, 32, 16 );
    return point.x_;
}
